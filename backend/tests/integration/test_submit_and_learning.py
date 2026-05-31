"""Submit flow integration + the knowledge-base learning loop."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.executor import execute_decision
from app.models import Decision


@pytest.fixture
def fake_provider(monkeypatch, temp_env):
    fake = MagicMock(name="EmailProvider")
    fake.send_reply.return_value = "sent"
    fake.create_draft.return_value = "drafted"
    fake.apply_label.return_value = "labeled"
    fake.archive.return_value = "archived"
    fake.health.return_value = (True, "ok")
    fake.name = "fake"
    from app import providers
    providers._provider = fake
    yield fake
    providers.reset_provider()


def _decision(db, **overrides) -> Decision:
    base = dict(
        id="d-1",
        email_id="m-1",
        thread_id="t-1",
        sender="Ann",
        sender_email="ann@x.com",
        subject="Q",
        snippet="hi",
        body="What is the price?",
        received_at="2026-05-29",
        matched_rule_id="r-1",
        matched_rule_name="r-1",
        confidence=0.9,
        safety_flag=False,
        sales_opportunity=False,
        reasoning="",
        action_type="reply",
        send_mode="draft",
        summary="x",
        proposed_draft="Hi Ann — the price is $2,500.",
        voice_used=None,
        knowledge_refs=[],
        label=None,
        handoff_payload=None,
        status="pending",
    )
    base.update(overrides)
    d = Decision(**base)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


class TestSubmitEachActionType:
    def test_reply_send_calls_send_reply(self, db, fake_provider, seed_brain):
        d = _decision(db, send_mode="send")
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.send_reply.assert_called_once()

    def test_reply_draft_calls_create_draft(self, db, fake_provider, seed_brain):
        d = _decision(db, send_mode="draft")
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.create_draft.assert_called_once()

    def test_flag_only_labels(self, db, fake_provider, seed_brain):
        d = _decision(db, action_type="flag", label="Needs review")
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.apply_label.assert_called_once_with(
            db.query(Decision).first() and pytest.helpers if False else fake_provider.apply_label.call_args.args[0],
            "Needs review",
        )

    def test_label_action_applies_named_label(self, db, fake_provider, seed_brain):
        d = _decision(db, action_type="label", label="Internal")
        ok, _ = execute_decision(db, d)
        assert ok
        assert fake_provider.apply_label.call_args.args[1] == "Internal"

    def test_discard_archives(self, db, fake_provider, seed_brain):
        d = _decision(db, action_type="discard")
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.archive.assert_called_once()

    def test_exclude_is_idempotent_noop(self, db, fake_provider, seed_brain):
        d = _decision(db, action_type="exclude", status="excluded")
        ok, msg = execute_decision(db, d)
        assert ok and "excluded" in msg.lower()
        fake_provider.send_reply.assert_not_called()
        fake_provider.create_draft.assert_not_called()
        fake_provider.apply_label.assert_not_called()
        fake_provider.archive.assert_not_called()


class TestStatusTransitions:
    def test_pending_to_submitted_on_success(self, db, fake_provider, seed_brain):
        d = _decision(db, send_mode="send")
        execute_decision(db, d)
        db.refresh(d)
        assert d.status == "submitted"
        assert d.executed_at is not None

    def test_pending_to_failed_on_exception(self, db, fake_provider, seed_brain):
        fake_provider.send_reply.side_effect = RuntimeError("api down")
        d = _decision(db, send_mode="send")
        execute_decision(db, d)
        db.refresh(d)
        assert d.status == "failed"
        assert "api down" in (d.execution_result or "")


class TestLearningLoop:
    def test_edited_draft_sent_instead_of_proposed(self, db, fake_provider, seed_brain):
        d = _decision(db, send_mode="send", proposed_draft="auto generated text")
        edited = "manually corrected reply"
        execute_decision(db, d, edited_draft=edited)
        # The wire body must be the EDITED text.
        sent_body = fake_provider.send_reply.call_args.args[1]
        assert sent_body == edited
        # And it's persisted to the decision row.
        db.refresh(d)
        assert d.user_edited_draft == edited

    def test_save_to_knowledge_appends_to_specified_file(
        self, db, fake_provider, seed_brain, temp_env
    ):
        before = (temp_env / "brain" / "knowledge" / "faq.md").read_text()

        d = _decision(
            db, send_mode="send",
            body="A new question that wasn't in the FAQ.",
        )
        execute_decision(
            db, d,
            edited_draft="The freshly-corrected answer.",
            save_to_knowledge="faq.md",
        )
        after = (temp_env / "brain" / "knowledge" / "faq.md").read_text()

        # Original content preserved.
        assert before in after
        # New Q&A appended.
        assert "A new question that wasn't in the FAQ." in after
        assert "The freshly-corrected answer." in after
        # As a proper Q&A section, not stitched into the existing one.
        assert "## Q: A new question" in after

    def test_save_to_knowledge_does_not_modify_unrelated_files(
        self, db, fake_provider, seed_brain, temp_env
    ):
        """Regression: writes to one file must not touch others (mirrors the
        brain-leak bug we found earlier)."""
        other = temp_env / "brain" / "knowledge" / "other.md"
        other.write_text("# other\n\n## Q: untouched\n\nuntouched\n", encoding="utf-8")
        before_other = other.read_text()
        before_guard = (temp_env / "brain" / "guardrails.md").read_text()

        d = _decision(db, send_mode="send", body="Q text")
        execute_decision(
            db, d, edited_draft="A text", save_to_knowledge="faq.md"
        )

        assert other.read_text() == before_other
        assert (temp_env / "brain" / "guardrails.md").read_text() == before_guard

    def test_save_to_knowledge_omitted_means_no_brain_change(
        self, db, fake_provider, seed_brain, temp_env
    ):
        snapshot = {
            p.name: p.read_text()
            for p in (temp_env / "brain" / "knowledge").iterdir()
        }
        d = _decision(db, send_mode="send")
        execute_decision(db, d, edited_draft="reply", save_to_knowledge=None)
        after = {
            p.name: p.read_text()
            for p in (temp_env / "brain" / "knowledge").iterdir()
        }
        assert snapshot == after
