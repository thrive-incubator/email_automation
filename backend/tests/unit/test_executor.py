"""Executor coverage — every action_type's submit path + every failure mode."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.executor import execute_decision
from app.models import AuditLog, Decision
from app.providers import reset_provider
from app.providers.base import EmailMessage


def _decision(action: str, **overrides) -> Decision:
    base = dict(
        id="d-test",
        email_id="m-test",
        thread_id="t-test",
        sender="Alex Tester",
        sender_email="alex@example.com",
        subject="Test",
        snippet="Hello",
        body="Hello body",
        received_at="2026-05-29",
        matched_rule_id="rule-x",
        matched_rule_name="rule-x",
        confidence=0.95,
        safety_flag=False,
        sales_opportunity=False,
        reasoning="ok",
        action_type=action,
        send_mode="draft",
        summary="x",
        proposed_draft="Hello — proposed reply body.",
        voice_used=None,
        knowledge_refs=[],
        label=None,
        handoff_payload=None,
        status="pending",
    )
    base.update(overrides)
    return Decision(**base)


@pytest.fixture
def fake_provider(monkeypatch, temp_env):
    """Swap the email provider for a MagicMock so we can assert exact calls."""
    fake = MagicMock(name="EmailProvider")
    fake.send_reply.return_value = "sent ok"
    fake.create_draft.return_value = "draft ok"
    fake.apply_label.return_value = "labeled ok"
    fake.archive.return_value = "archived ok"
    fake.health.return_value = (True, "ok")
    fake.name = "fake"

    from app import providers
    providers._provider = fake
    yield fake
    reset_provider()


# ── Reply: send mode ────────────────────────────────────────────────────────--
class TestReplyAction:
    def test_send_mode_calls_send_reply(self, db, fake_provider):
        d = _decision("reply", send_mode="send")
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert ok and "sent" in msg.lower()
        fake_provider.send_reply.assert_called_once()
        fake_provider.create_draft.assert_not_called()
        db.refresh(d)
        assert d.status == "submitted"
        assert d.executed_at is not None

    def test_draft_mode_calls_create_draft(self, db, fake_provider):
        d = _decision("reply", send_mode="draft")
        db.add(d); db.commit(); db.refresh(d)
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.create_draft.assert_called_once()
        fake_provider.send_reply.assert_not_called()

    def test_edited_draft_overrides_proposed(self, db, fake_provider):
        d = _decision("reply", send_mode="send")
        db.add(d); db.commit(); db.refresh(d)
        edited = "User-edited reply text."
        execute_decision(db, d, edited_draft=edited)
        call = fake_provider.send_reply.call_args
        assert call.args[1] == edited
        db.refresh(d)
        assert d.user_edited_draft == edited

    def test_empty_body_fails_cleanly(self, db, fake_provider):
        d = _decision("reply", send_mode="send", proposed_draft="")
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert not ok
        assert "empty" in msg.lower()
        db.refresh(d)
        assert d.status == "failed"
        fake_provider.send_reply.assert_not_called()


# ── Label / discard / flag / handoff / exclude ──────────────────────────────--
class TestNonReplyActions:
    def test_label_applies_provider_label(self, db, fake_provider):
        d = _decision("label", label="Internal")
        db.add(d); db.commit(); db.refresh(d)
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.apply_label.assert_called_once()
        assert fake_provider.apply_label.call_args.args[1] == "Internal"

    def test_label_falls_back_to_default_when_missing(self, db, fake_provider):
        d = _decision("label", label=None)
        db.add(d); db.commit(); db.refresh(d)
        execute_decision(db, d)
        assert fake_provider.apply_label.call_args.args[1] == "Auto-handled"

    def test_discard_archives(self, db, fake_provider):
        d = _decision("discard")
        db.add(d); db.commit(); db.refresh(d)
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.archive.assert_called_once()

    def test_flag_applies_review_label(self, db, fake_provider):
        d = _decision("flag", label="Needs review")
        db.add(d); db.commit(); db.refresh(d)
        ok, _ = execute_decision(db, d)
        assert ok
        fake_provider.apply_label.assert_called_once()
        assert fake_provider.apply_label.call_args.args[1] == "Needs review"

    def test_exclude_is_a_noop_against_provider(self, db, fake_provider):
        """Excluded decisions are auto-final at creation; resubmitting them must
        NEVER touch Gmail."""
        d = _decision("exclude", status="excluded")
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert ok
        assert "excluded" in msg.lower()
        fake_provider.send_reply.assert_not_called()
        fake_provider.create_draft.assert_not_called()
        fake_provider.apply_label.assert_not_called()
        fake_provider.archive.assert_not_called()


# ── CRM handoff ─────────────────────────────────────────────────────────────--
class TestCrmHandoff:
    def test_handoff_writes_to_local_outbox_when_no_webhook(
        self, db, fake_provider, temp_env, monkeypatch
    ):
        monkeypatch.setenv("CRM_WEBHOOK_URL", "")
        from app import config
        config.get_settings.cache_clear()

        d = _decision(
            "crm_handoff",
            handoff_payload={"contact_name": "Alex", "intent": "wants demo"},
        )
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert ok
        assert "outbox" in msg.lower()

        outbox = temp_env / "data" / "crm_outbox.jsonl"
        assert outbox.exists()
        lines = outbox.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["contact_name"] == "Alex"
        assert record["intent"] == "wants demo"
        assert "at" in record  # timestamp

    def test_handoff_posts_to_webhook_when_configured(
        self, db, fake_provider, monkeypatch
    ):
        from app import executor
        captured = {}

        class _Resp:
            status_code = 200
            def raise_for_status(self):
                pass

        def _fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            return _Resp()

        monkeypatch.setattr(executor.httpx, "post", _fake_post)
        monkeypatch.setenv("CRM_WEBHOOK_URL", "https://example.com/hook")
        from app import config
        config.get_settings.cache_clear()

        d = _decision("crm_handoff", handoff_payload={"intent": "buy"})
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert ok
        assert "200" in msg or "webhook" in msg.lower()
        assert captured["url"] == "https://example.com/hook"
        assert captured["json"]["intent"] == "buy"

    def test_handoff_also_labels_when_label_set(self, db, fake_provider, monkeypatch):
        monkeypatch.setenv("CRM_WEBHOOK_URL", "")
        from app import config
        config.get_settings.cache_clear()

        d = _decision("crm_handoff", label="Lead", handoff_payload={"a": 1})
        db.add(d); db.commit(); db.refresh(d)
        execute_decision(db, d)
        fake_provider.apply_label.assert_called_once()
        assert fake_provider.apply_label.call_args.args[1] == "Lead"


# ── Lifecycle / status transitions ──────────────────────────────────────────--
class TestLifecycle:
    def test_idempotent_on_already_submitted(self, db, fake_provider):
        d = _decision(
            "reply", send_mode="send", status="submitted",
            executed_at=datetime.now(timezone.utc),
        )
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert ok
        assert "already" in msg.lower()
        fake_provider.send_reply.assert_not_called()

    def test_failure_marks_status_failed_and_records_error(
        self, db, fake_provider
    ):
        fake_provider.send_reply.side_effect = RuntimeError("gmail boom")
        d = _decision("reply", send_mode="send")
        db.add(d); db.commit(); db.refresh(d)
        ok, msg = execute_decision(db, d)
        assert not ok
        assert "boom" in msg
        db.refresh(d)
        assert d.status == "failed"
        assert "boom" in (d.execution_result or "")

    def test_audit_log_appended_on_success(self, db, fake_provider):
        d = _decision("reply", send_mode="send")
        db.add(d); db.commit(); db.refresh(d)
        execute_decision(db, d)
        rows = db.query(AuditLog).filter_by(decision_id="d-test").all()
        assert any("executed" in r.event for r in rows)

    def test_audit_log_appended_on_failure(self, db, fake_provider):
        fake_provider.send_reply.side_effect = RuntimeError("nope")
        d = _decision("reply", send_mode="send")
        db.add(d); db.commit(); db.refresh(d)
        execute_decision(db, d)
        rows = db.query(AuditLog).filter_by(decision_id="d-test").all()
        assert any(r.event == "failed" for r in rows)


# ── Learning loop ───────────────────────────────────────────────────────────--
class TestLearningLoop:
    def test_save_to_knowledge_appends_correction(
        self, db, fake_provider, seed_brain, temp_env
    ):
        d = _decision(
            "reply", send_mode="send",
            body="Original incoming question text.",
        )
        db.add(d); db.commit(); db.refresh(d)
        edited = "The correct, hand-written answer."
        ok, _ = execute_decision(
            db, d, edited_draft=edited, save_to_knowledge="faq.md"
        )
        assert ok
        content = (temp_env / "brain" / "knowledge" / "faq.md").read_text()
        # The original Q got appended as a new section, with the corrected answer.
        assert "Original incoming question text." in content
        assert "The correct, hand-written answer." in content
        # Earlier content not destroyed.
        assert "Sample answer." in content

    def test_save_to_knowledge_does_not_touch_other_files(
        self, db, fake_provider, seed_brain, temp_env
    ):
        """Edits to one knowledge file must NOT leak into another. Regression for
        the kind of bug we already caught in brain.read_all_knowledge."""
        other = temp_env / "brain" / "knowledge" / "other.md"
        other.write_text("# Other\n\n## Q: keep\n\nUntouched.\n", encoding="utf-8")
        before = other.read_text()

        d = _decision("reply", send_mode="send", body="Q text")
        db.add(d); db.commit(); db.refresh(d)
        execute_decision(db, d, edited_draft="A text", save_to_knowledge="faq.md")

        assert other.read_text() == before, "writing to faq.md leaked into other.md"
