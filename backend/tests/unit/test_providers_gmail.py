"""GmailProvider with a fully stubbed Google API client.

We never hit the network. Instead, we build a fake `service` object that mirrors
the chained-method pattern Google's discovery client uses
(svc.users().messages().list(...).execute()) and assert on what would be sent.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from app.providers.base import EmailMessage
from app.providers.gmail import GmailProvider


def _exec(value):
    """Helper: turn a value into a chained `.execute()` mock."""
    m = MagicMock()
    m.execute.return_value = value
    return m


def _fake_message(
    mid: str = "m-1",
    thread_id: str = "t-1",
    from_addr: str = "alice@example.com",
    from_name: str = "Alice",
    subject: str = "Hello",
    body: str = "Hi there!",
    snippet: str = "Hi there!",
    internal_date: int = 1700000000000,
) -> dict:
    """Construct a Gmail API message resource that matches the real shape."""
    return {
        "id": mid,
        "threadId": thread_id,
        "snippet": snippet,
        "internalDate": str(internal_date),
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": f"{from_name} <{from_addr}>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 1 Jan 2026 10:00:00 +0000"},
                {"name": "Message-ID", "value": f"<{mid}@mail>"},
                {"name": "To", "value": "me@example.com"},
            ],
            "body": {
                "data": base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
            },
        },
    }


def _build_provider(monkeypatch, service_mock):
    """GmailProvider wired to a fake service; OAuth helpers stubbed."""
    p = GmailProvider()
    monkeypatch.setattr(p, "_get_service", lambda: service_mock)
    monkeypatch.setattr(p, "_get_me_email", lambda: "me@example.com")
    return p


# ── fetch_unread happy path ─────────────────────────────────────────────────--
class TestFetchUnread:
    def test_returns_one_email_per_thread(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().list = MagicMock(
            return_value=_exec({"messages": [{"id": "m-1"}, {"id": "m-2"}]})
        )
        # The metadata-only call (used to learn threadId)
        svc.users().messages().get = MagicMock(
            side_effect=[
                _exec({"threadId": "t-1"}),
                _exec({"threadId": "t-2"}),
            ]
        )
        svc.users().threads().get = MagicMock(
            side_effect=[
                _exec({"messages": [_fake_message("m-1", "t-1", from_addr="alice@example.com")]}),
                _exec({"messages": [_fake_message("m-2", "t-2", from_addr="bob@example.com")]}),
            ]
        )
        p = _build_provider(monkeypatch, svc)
        out = p.fetch_unread()
        assert len(out) == 2
        assert {e.sender_email for e in out} == {"alice@example.com", "bob@example.com"}

    def test_since_days_appends_newer_than_to_query(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().list = MagicMock(return_value=_exec({"messages": []}))
        p = _build_provider(monkeypatch, svc)
        p.fetch_unread(since_days=7)
        list_call = svc.users().messages().list.call_args
        assert "newer_than:7d" in list_call.kwargs["q"]
        assert "is:unread" in list_call.kwargs["q"]

    def test_no_since_days_omits_newer_than(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().list = MagicMock(return_value=_exec({"messages": []}))
        p = _build_provider(monkeypatch, svc)
        p.fetch_unread(since_days=None)
        assert "newer_than" not in svc.users().messages().list.call_args.kwargs["q"]


# ── waiting_on_me: skip threads I sent last ─────────────────────────────────--
class TestWaitingOnMe:
    def test_skips_thread_where_i_sent_last(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().list = MagicMock(
            return_value=_exec({"messages": [{"id": "m-1"}, {"id": "m-2"}]})
        )
        svc.users().messages().get = MagicMock(
            side_effect=[_exec({"threadId": "t-1"}), _exec({"threadId": "t-2"})]
        )
        # Thread t-1: latest message is from ME → must be skipped.
        # Thread t-2: latest is from someone else → must be kept.
        svc.users().threads().get = MagicMock(
            side_effect=[
                _exec({
                    "messages": [
                        _fake_message("m-1-old", "t-1", from_addr="external@x.com", internal_date=100),
                        _fake_message("m-1", "t-1", from_addr="me@example.com", internal_date=200),
                    ]
                }),
                _exec({
                    "messages": [
                        _fake_message("m-2", "t-2", from_addr="bob@example.com", internal_date=300),
                    ]
                }),
            ]
        )
        p = _build_provider(monkeypatch, svc)
        out = p.fetch_unread(waiting_on_me=True)
        assert len(out) == 1
        assert out[0].sender_email == "bob@example.com"

    def test_disabling_filter_includes_all_threads(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().list = MagicMock(
            return_value=_exec({"messages": [{"id": "m-1"}, {"id": "m-2"}]})
        )
        svc.users().messages().get = MagicMock(
            side_effect=[_exec({"threadId": "t-1"}), _exec({"threadId": "t-2"})]
        )
        svc.users().threads().get = MagicMock(
            side_effect=[
                _exec({"messages": [_fake_message("m-1", "t-1", from_addr="me@example.com")]}),
                _exec({"messages": [_fake_message("m-2", "t-2", from_addr="bob@example.com")]}),
            ]
        )
        p = _build_provider(monkeypatch, svc)
        out = p.fetch_unread(waiting_on_me=False)
        assert len(out) == 2

    def test_dedupes_multiple_unread_in_same_thread(self, temp_env, monkeypatch):
        """One thread, two unread messages → we should act on the latest only."""
        svc = MagicMock()
        svc.users().messages().list = MagicMock(
            return_value=_exec({"messages": [{"id": "m-old"}, {"id": "m-new"}]})
        )
        # Both messages belong to the same thread.
        svc.users().messages().get = MagicMock(
            side_effect=[_exec({"threadId": "t-1"}), _exec({"threadId": "t-1"})]
        )
        svc.users().threads().get = MagicMock(
            return_value=_exec({
                "messages": [
                    _fake_message("m-old", "t-1", from_addr="x@x.com", internal_date=100),
                    _fake_message("m-new", "t-1", from_addr="x@x.com", internal_date=200),
                ]
            })
        )
        p = _build_provider(monkeypatch, svc)
        out = p.fetch_unread()
        assert len(out) == 1
        assert out[0].id == "m-new"


# ── send_reply / create_draft MIME structure ────────────────────────────────--
class TestSendReplyMime:
    def _make_email(self) -> EmailMessage:
        return EmailMessage(
            id="m-orig",
            thread_id="t-orig",
            sender="Alice",
            sender_email="alice@example.com",
            subject="Question",
            snippet="",
            body="",
            rfc822_message_id="<orig@mail>",
        )

    def _decode(self, raw_b64: str) -> str:
        # Gmail API wants urlsafe-base64 without padding; restore it.
        pad = "=" * (-len(raw_b64) % 4)
        return base64.urlsafe_b64decode(raw_b64 + pad).decode()

    def test_send_reply_in_thread_marks_unread_removed(self, temp_env, monkeypatch):
        svc = MagicMock()
        sent = []
        modified = []

        def _send(**kwargs):
            sent.append(kwargs)
            return _exec({"id": "sent-id"})

        def _modify(**kwargs):
            modified.append(kwargs)
            return _exec({})

        svc.users().messages().send = MagicMock(side_effect=_send)
        svc.users().messages().modify = MagicMock(side_effect=_modify)

        p = _build_provider(monkeypatch, svc)
        result = p.send_reply(self._make_email(), "Reply body text")
        assert "sent-id" in result

        body = sent[0]["body"]
        assert body["threadId"] == "t-orig"
        raw = self._decode(body["raw"])
        assert "Re: Question" in raw
        assert "In-Reply-To: <orig@mail>" in raw
        assert "References: <orig@mail>" in raw
        assert "To: alice@example.com" in raw
        assert "Reply body text" in raw

        # Also marks the message read.
        assert any("UNREAD" in str(m["body"]) for m in modified)

    def test_subject_prefix_not_doubled(self, temp_env, monkeypatch):
        svc = MagicMock()
        sent = []
        svc.users().messages().send = MagicMock(
            side_effect=lambda **kw: (sent.append(kw), _exec({"id": "x"}))[1]
        )
        svc.users().messages().modify = MagicMock(return_value=_exec({}))

        p = _build_provider(monkeypatch, svc)
        e = self._make_email()
        e.subject = "RE: ALREADY PREFIXED"
        p.send_reply(e, "body")
        raw = self._decode(sent[0]["body"]["raw"])
        # Should NOT double-prefix "Re: Re: ..."
        assert raw.count("Re:") == 1 or raw.count("RE:") == 1

    def test_create_draft_uses_drafts_endpoint(self, temp_env, monkeypatch):
        svc = MagicMock()
        created = []
        svc.users().drafts().create = MagicMock(
            side_effect=lambda **kw: (created.append(kw), _exec({"id": "d-x"}))[1]
        )
        p = _build_provider(monkeypatch, svc)
        result = p.create_draft(self._make_email(), "Draft body")
        assert "d-x" in result
        assert created[0]["body"]["message"]["threadId"] == "t-orig"


# ── label / archive ─────────────────────────────────────────────────────────--
class TestLabelArchive:
    def test_apply_label_creates_label_if_missing_then_modifies(
        self, temp_env, monkeypatch
    ):
        svc = MagicMock()
        # Existing labels list — none of them match "New Label".
        svc.users().labels().list = MagicMock(
            return_value=_exec({"labels": [{"id": "Label_existing", "name": "Existing"}]})
        )
        svc.users().labels().create = MagicMock(
            return_value=_exec({"id": "Label_new", "name": "New Label"})
        )
        modified = []
        svc.users().messages().modify = MagicMock(
            side_effect=lambda **kw: (modified.append(kw), _exec({}))[1]
        )

        p = _build_provider(monkeypatch, svc)
        e = EmailMessage(
            id="m-1", thread_id="t-1", sender="A", sender_email="a@a.com",
            subject="x", snippet="", body=""
        )
        p.apply_label(e, "New Label")
        svc.users().labels().create.assert_called_once()
        assert "Label_new" in modified[0]["body"]["addLabelIds"]

    def test_archive_removes_unread_and_inbox(self, temp_env, monkeypatch):
        svc = MagicMock()
        modified = []
        svc.users().messages().modify = MagicMock(
            side_effect=lambda **kw: (modified.append(kw), _exec({}))[1]
        )
        p = _build_provider(monkeypatch, svc)
        e = EmailMessage(
            id="m-1", thread_id="t-1", sender="A", sender_email="a@a.com",
            subject="x", snippet="", body=""
        )
        p.archive(e)
        removed = modified[0]["body"]["removeLabelIds"]
        assert "UNREAD" in removed and "INBOX" in removed


# ── fetch_by_ids ────────────────────────────────────────────────────────────--
class TestFetchByIds:
    def test_returns_one_email_message_per_id(self, temp_env, monkeypatch):
        svc = MagicMock()
        svc.users().messages().get = MagicMock(
            side_effect=[
                _exec(_fake_message("m-1", "t-1", from_addr="x@x.com")),
                _exec(_fake_message("m-2", "t-2", from_addr="y@y.com")),
            ]
        )
        p = _build_provider(monkeypatch, svc)
        out = p.fetch_by_ids(["m-1", "m-2"])
        assert [e.id for e in out] == ["m-1", "m-2"]
        assert out[0].sender_email == "x@x.com"

    def test_empty_input_returns_empty(self, temp_env, monkeypatch):
        p = _build_provider(monkeypatch, MagicMock())
        assert p.fetch_by_ids([]) == []


# ── Health & OAuth helpers ──────────────────────────────────────────────────--
class TestHealthAndAuth:
    def test_health_reports_disconnected_when_no_token(self, temp_env, monkeypatch):
        p = GmailProvider()
        # is_connected reads token file at the configured path; the temp env
        # has no token, so disconnected.
        ok, detail = p.health()
        assert not ok
        assert "not connected" in detail.lower()
