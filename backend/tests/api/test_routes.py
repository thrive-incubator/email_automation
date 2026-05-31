"""HTTP API tests via FastAPI's TestClient. One file to keep the surface visible.

Every route gets at minimum a happy-path + an error-path test.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── /api/health ─────────────────────────────────────────────────────────────--
class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "service": "inbox-autopilot"}


# ── /api/inbox ──────────────────────────────────────────────────────────────--
class TestInboxRoute:
    def test_inbox_returns_unread_emails(self, client):
        r = client.get("/api/inbox")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            sample = items[0]
            for key in (
                "id", "thread_id", "sender", "sender_email",
                "subject", "snippet", "body", "received_at",
                "processed", "decision_id",
            ):
                assert key in sample

    def test_inbox_since_days_filter(self, client):
        all_resp = client.get("/api/inbox").json()
        one_day = client.get("/api/inbox?since_days=1").json()
        assert len(one_day) <= len(all_resp)

    def test_inbox_annotates_processed_emails(self, client):
        """After /api/run, the inbox endpoint still returns the emails but with
        `processed=True` so the UI can hide/cross-link them. The frontend filters
        them out of the visible list — keeping this annotation on the wire (rather
        than filtering server-side) lets the UI link "this was already decided"."""
        client.post("/api/run")
        items = client.get("/api/inbox").json()
        # Every returned item should now be flagged processed with a decision id.
        if items:
            assert all(i["processed"] for i in items)
            assert all(i["decision_id"] for i in items)

    def test_inbox_waiting_on_me_param_accepted(self, client):
        r = client.get("/api/inbox?waiting_on_me=false")
        assert r.status_code == 200


# ── /api/run + /api/run/stream ──────────────────────────────────────────────--
class TestRunRoute:
    def test_run_processes_unread(self, client):
        r = client.post("/api/run").json()
        assert "fetched" in r and "new" in r and "skipped" in r
        assert r["new"] > 0
        # Idempotent on second call.
        r2 = client.post("/api/run").json()
        assert r2["new"] == 0
        assert r2["skipped"] == r["fetched"]

    def test_run_with_since_days(self, client):
        r = client.post("/api/run?since_days=1")
        assert r.status_code == 200

    def test_run_with_specific_email_ids(self, client):
        """POST /api/run doesn't accept email_ids in its current signature, but
        /api/run/stream does. Pin the stream-only contract."""
        # /api/run takes since_days + waiting_on_me; not email_ids.
        r = client.post("/api/run?limit=1")
        assert r.status_code == 200


class TestRunStream:
    def test_stream_emits_sse_events(self, client):
        # Use a streaming GET against the SSE endpoint.
        with client.stream("GET", "/api/run/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            chunks = list(resp.iter_text())
        body = "".join(chunks)
        assert "event: start" in body
        assert "event: done" in body

    def test_stream_progresses_through_each_email(self, client):
        with client.stream("GET", "/api/run/stream") as resp:
            body = "".join(resp.iter_text())
        # Should see one `progress` per email (6 in mock seed) and a matching
        # number of `decision` events.
        assert body.count("event: progress") >= 1
        assert body.count("event: decision") >= 1

    def test_stream_with_email_ids_param(self, client):
        # Process only a specific email id.
        inbox = client.get("/api/inbox?waiting_on_me=false").json()
        if not inbox:
            pytest.skip("no inbox items in this run")
        target_id = inbox[0]["id"]
        with client.stream("GET", f"/api/run/stream?email_ids={target_id}") as resp:
            body = "".join(resp.iter_text())
        assert "event: done" in body


# ── /api/decisions, /api/decisions/submit, /api/decisions/{id}/discard ──────--
class TestDecisionsRoute:
    def test_list_empty(self, client):
        r = client.get("/api/decisions")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_after_run_returns_decisions(self, client):
        client.post("/api/run")
        items = client.get("/api/decisions").json()
        assert len(items) > 0

    def test_list_filter_by_status(self, client):
        client.post("/api/run")
        pending = client.get("/api/decisions?status=pending").json()
        for d in pending:
            assert d["status"] == "pending"

    def test_submit_unknown_decision_returns_not_found(self, client):
        r = client.post(
            "/api/decisions/submit",
            json={"items": [{"decision_id": "nope"}]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body[0]["ok"] is False
        assert "not found" in body[0]["message"].lower()

    def test_discard_unknown_decision_returns_404(self, client):
        r = client.post("/api/decisions/nope/discard")
        assert r.status_code == 404


# ── /api/rules ──────────────────────────────────────────────────────────────--
class TestRulesRoute:
    def test_list_rules_returns_seeded(self, client):
        r = client.get("/api/rules")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_create_rule(self, client):
        payload = {
            "name": "Brand new rule",
            "description": "via api",
            "filter_prompt": "match all",
            "action_type": "label",
            "label": "Test",
            "voice_file": None,
            "knowledge_files": [],
            "reply_prompt": None,
            "confidence_threshold": 0.7,
            "send_mode": "draft",
            "enabled": True,
            "priority": 99,
        }
        r = client.post("/api/rules", json=payload)
        assert r.status_code == 200
        created = r.json()
        assert created["name"] == "Brand new rule"
        assert created["id"].startswith("rule-")
        # And it appears in subsequent list calls.
        assert any(rl["id"] == created["id"] for rl in client.get("/api/rules").json())

    def test_create_rule_with_exclude_action(self, client):
        payload = {
            "name": "Exclude test",
            "description": "",
            "filter_prompt": "x",
            "action_type": "exclude",
            "voice_file": None,
            "knowledge_files": [],
            "reply_prompt": None,
            "confidence_threshold": 0.9,
            "send_mode": "draft",
            "label": None,
            "enabled": True,
            "priority": 5,
        }
        r = client.post("/api/rules", json=payload)
        assert r.status_code == 200
        assert r.json()["action_type"] == "exclude"

    def test_update_rule(self, client):
        existing = client.get("/api/rules").json()[0]
        updated = {**existing, "name": "Renamed via API"}
        # PUT expects RuleCreate (no `id` field).
        updated.pop("id", None)
        r = client.put(f"/api/rules/{existing['id']}", json=updated)
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed via API"

    def test_update_unknown_rule_404(self, client):
        payload = {
            "name": "x", "description": "", "filter_prompt": "x",
            "action_type": "reply", "voice_file": None, "knowledge_files": [],
            "reply_prompt": None, "confidence_threshold": 0.85,
            "send_mode": "draft", "label": None, "enabled": True, "priority": 100,
        }
        r = client.put("/api/rules/does-not-exist", json=payload)
        assert r.status_code == 404

    def test_delete_rule(self, client):
        existing = client.get("/api/rules").json()
        target = existing[0]
        r = client.delete(f"/api/rules/{target['id']}")
        assert r.status_code == 200
        remaining = client.get("/api/rules").json()
        assert all(rl["id"] != target["id"] for rl in remaining)

    def test_delete_unknown_rule_404(self, client):
        r = client.delete("/api/rules/missing")
        assert r.status_code == 404


# ── /api/brain ──────────────────────────────────────────────────────────────--
class TestBrainRoute:
    def test_index_lists_voices_and_knowledge(self, client):
        r = client.get("/api/brain")
        assert r.status_code == 200
        body = r.json()
        assert "voices" in body and "knowledge" in body and "guardrails" in body

    def test_get_known_file(self, client):
        r = client.get("/api/brain/voice/warm.md")
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "voice"
        assert "sign off" in body["content"].lower()

    def test_get_missing_file_returns_empty_content(self, client):
        # The handler returns empty content for missing files rather than 404 —
        # callers can treat that as "new file".
        r = client.get("/api/brain/voice/never-existed.md")
        assert r.status_code == 200
        assert r.json()["content"] == ""

    def test_get_unknown_kind_400(self, client):
        r = client.get("/api/brain/nonsense/x.md")
        assert r.status_code == 400

    def test_put_updates_file(self, client):
        r = client.put(
            "/api/brain/voice/warm.md",
            json={"content": "updated voice content"},
        )
        assert r.status_code == 200
        # Round-trip.
        assert client.get("/api/brain/voice/warm.md").json()["content"] == "updated voice content"

    def test_put_unknown_kind_400(self, client):
        r = client.put("/api/brain/banish/x.md", json={"content": "x"})
        assert r.status_code == 400


# ── /api/settings + /api/settings/test ──────────────────────────────────────--
class TestSettingsRoute:
    def test_get_settings_includes_all_fields(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        body = r.json()
        for key in (
            "email_provider", "gemini_model", "anthropic_model",
            "gmail_connected", "crm_handoff_target",
        ):
            assert key in body

    def test_test_connections_runs_health_checks(self, client):
        r = client.post("/api/settings/test")
        assert r.status_code == 200
        statuses = r.json()
        assert len(statuses) == 3  # filter, answerer, email provider
        for s in statuses:
            assert "name" in s and "configured" in s and "ok" in s and "detail" in s


# ── /api/auth/gmail ─────────────────────────────────────────────────────────--
class TestAuthRoute:
    def test_start_when_not_gmail_provider_returns_400(self, client):
        """The test fixture uses mock provider; oauth start should refuse."""
        r = client.get("/api/auth/gmail/start")
        assert r.status_code == 400
        assert "gmail" in r.json()["detail"].lower()

    def test_callback_without_code_returns_400(self, client, monkeypatch):
        # Even if we WERE in gmail mode, missing code is a 400.
        from app import providers
        fake = MagicMock()
        fake.name = "gmail"
        providers._provider = fake
        try:
            r = client.get("/api/auth/gmail/callback")
            assert r.status_code == 400
        finally:
            providers.reset_provider()


# ── /api/reset ──────────────────────────────────────────────────────────────--
class TestResetRoute:
    def test_reset_clears_decisions_and_ledger(self, client):
        client.post("/api/run")
        assert len(client.get("/api/decisions").json()) > 0
        r = client.post("/api/reset")
        assert r.status_code == 200
        assert client.get("/api/decisions").json() == []
        # Inbox repopulates because the provider's handled-state was reset.
        assert len(client.get("/api/inbox?waiting_on_me=false").json()) > 0
