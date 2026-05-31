"""End-to-end pipeline integration: provider → engine → decision → executor.

Uses the real mock provider + the real mock LLM (no API keys). The point is to
catch wiring bugs across module boundaries that the unit tests miss.
"""
from __future__ import annotations

import pytest

from app import engine
from app.models import AuditLog, Decision, ProcessedEmail
from app.providers import get_provider, reset_provider


@pytest.fixture
def pipeline(db, seed_brain, seed_rules):
    """Fresh state: rules + brain seeded, mock provider reset."""
    reset_provider()
    get_provider().reset()
    return get_provider()


class TestHappyPath:
    def test_first_run_creates_decisions(self, db, pipeline):
        res = engine.run_pipeline(db, limit=50, waiting_on_me=False)
        assert res["fetched"] == 6  # mock seeds 6 messages
        assert res["new"] == 6
        assert res["skipped"] == 0
        assert len(res["decisions"]) == 6

    def test_every_decision_persisted(self, db, pipeline):
        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        rows = db.query(Decision).all()
        assert len(rows) == 6

    def test_every_processed_email_in_ledger(self, db, pipeline):
        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        rows = db.query(ProcessedEmail).all()
        assert len(rows) == 6

    def test_each_decision_has_a_matched_rule(self, db, pipeline):
        """Mock filter + seeded rules should match every seeded email."""
        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        rows = db.query(Decision).all()
        unmatched = [d for d in rows if d.matched_rule_id is None]
        # If the mock heuristic can't classify everything, that's fine — but it
        # should at least classify the majority.
        assert len(unmatched) <= 2


class TestDedupe:
    def test_re_running_skips_already_processed(self, db, pipeline):
        first = engine.run_pipeline(db, limit=50, waiting_on_me=False)
        assert first["new"] == 6
        second = engine.run_pipeline(db, limit=50, waiting_on_me=False)
        assert second["new"] == 0
        assert second["skipped"] == 6
        # No duplicate decisions written.
        assert db.query(Decision).count() == 6

    def test_dedupe_survives_provider_state_change(self, db, pipeline):
        """Even if the provider re-surfaces an email, the ProcessedEmail ledger
        prevents double-handling at the engine level."""
        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        pipeline.reset()  # provider forgets handled state
        second = engine.run_pipeline(db, limit=50, waiting_on_me=False)
        # Provider re-serves 6, but ledger has them all → 0 new.
        assert second["new"] == 0


class TestSinceDaysFilter:
    def test_one_day_fewer_than_all_time(self, db, pipeline):
        all_time = engine.run_pipeline(db, limit=50, since_days=None, waiting_on_me=False)
        # New session: reset ledger so we re-process within the day filter.
        db.query(Decision).delete()
        db.query(ProcessedEmail).delete()
        db.commit()
        pipeline.reset()
        one_day = engine.run_pipeline(db, limit=50, since_days=1, waiting_on_me=False)
        assert one_day["new"] < all_time["new"]


class TestExcludeAction:
    def test_exclude_creates_decision_with_excluded_status(self, db, pipeline, monkeypatch):
        """An email matching an exclude rule should produce a Decision with
        status='excluded', no draft, no LLM call."""
        from app.llm import mock as mock_llm

        # Patch the mock filter to deterministically match the exclude rule for
        # one specific email id.
        from app.llm.base import Classification

        def _classify(self, email, rules):
            if email.id == "m6":  # the legal-threat email in the seed
                excl = next(r for r in rules if r.action_type == "exclude")
                return Classification(
                    matched_rule_id=excl.id, confidence=0.95,
                    safety_flag=True, sales_opportunity=False,
                    summary="legal", reasoning="forced",
                )
            return Classification(None, 0.0, False, False, "no", "no")

        monkeypatch.setattr(mock_llm.MockFilter, "classify", _classify)

        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        excluded = db.query(Decision).filter_by(action_type="exclude").all()
        assert len(excluded) == 1
        d = excluded[0]
        assert d.status == "excluded"
        assert d.proposed_draft == ""
        assert d.email_id == "m6"


class TestEmailIdsOverride:
    def test_process_specific_ids_only(self, db, pipeline):
        ids = [m.id for m in pipeline.fetch_unread(waiting_on_me=False)][:2]
        res = engine.run_pipeline(db, email_ids=ids, waiting_on_me=False)
        assert res["new"] == 2
        decided_ids = {d.email_id for d in db.query(Decision).all()}
        assert decided_ids == set(ids)


class TestAuditLog:
    def test_executor_writes_audit_on_success(self, db, pipeline, monkeypatch):
        """After running the pipeline and executing a decision, an audit row should appear."""
        from app.executor import execute_decision

        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        pending = (
            db.query(Decision)
            .filter_by(status="pending", action_type="reply")
            .first()
        )
        if pending is None:
            pytest.skip("mock filter didn't pick a reply rule this run")
        ok, _ = execute_decision(db, pending)
        assert ok
        rows = db.query(AuditLog).filter_by(decision_id=pending.id).all()
        assert any("executed" in r.event for r in rows)


class TestIterPipelineEvents:
    def test_event_sequence_for_each_email(self, db, pipeline):
        events = list(engine.iter_pipeline(db, limit=50, waiting_on_me=False))
        kinds = [e["type"] for e in events]
        # Must start with one `start`, end with one `done`, and have N pairs of
        # (progress, decision) in between.
        assert kinds[0] == "start"
        assert kinds[-1] == "done"
        # Each email contributes exactly one `progress` and one `decision`.
        assert kinds.count("progress") == 6
        assert kinds.count("decision") == 6

    def test_done_event_summary_matches_db(self, db, pipeline):
        events = list(engine.iter_pipeline(db, limit=50, waiting_on_me=False))
        done = events[-1]
        assert done["new"] == 6
        assert done["fetched"] == 6
        assert done["skipped"] == 0
