"""MockProvider behavior — seeded inbox, dedupe, since_days, fetch_by_ids."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.providers.mock import MockProvider


@pytest.fixture
def mock(temp_env):
    """Fresh MockProvider; persistence file lives under the test data dir."""
    p = MockProvider()
    p.reset()
    return p


class TestSeedInbox:
    def test_seed_has_six_messages(self, mock):
        out = mock.fetch_unread()
        assert len(out) == 6
        # Distinct ids, distinct senders.
        assert len({m.id for m in out}) == 6
        assert all(m.sender_email for m in out)

    def test_received_at_is_iso_with_timezone(self, mock):
        for m in mock.fetch_unread():
            dt = datetime.fromisoformat(m.received_at)
            assert dt.tzinfo is not None, "all timestamps must be tz-aware"

    def test_seed_ages_span_minutes_to_weeks(self, mock):
        ages_days = []
        now = datetime.now(timezone.utc)
        for m in mock.fetch_unread():
            ages_days.append((now - datetime.fromisoformat(m.received_at)).days)
        assert min(ages_days) == 0  # something fresh today
        assert max(ages_days) >= 14  # something older than 2 weeks


class TestSinceDaysFilter:
    @pytest.mark.parametrize(
        "days,expected_min,expected_max",
        [
            (1, 1, 3),    # 15m + 2h
            (7, 3, 5),    # +1d, 3d
            (30, 6, 6),   # everything
        ],
    )
    def test_filter_window(self, mock, days, expected_min, expected_max):
        out = mock.fetch_unread(since_days=days)
        assert expected_min <= len(out) <= expected_max

    def test_none_returns_all(self, mock):
        assert len(mock.fetch_unread(since_days=None)) == 6

    def test_zero_days_returns_only_today(self, mock):
        # since_days=0 means "newer than 0 days ago" — only this instant.
        out = mock.fetch_unread(since_days=0)
        # Mock provider treats 0 as a real cutoff (now - 0 = now); anything
        # older is filtered. Tolerate 0 or 1 (15m might or might not pass).
        assert len(out) <= 2

    def test_waiting_on_me_is_noop_for_mock(self, mock):
        """Mock has no threads; the toggle must not change the result."""
        assert mock.fetch_unread(waiting_on_me=True) == mock.fetch_unread(
            waiting_on_me=False
        )


class TestDedupeViaHandledState:
    def test_after_action_message_disappears(self, mock):
        first = mock.fetch_unread()
        target = first[0]
        mock.send_reply(target, "hi")
        remaining = mock.fetch_unread()
        assert target.id not in {m.id for m in remaining}
        assert len(remaining) == len(first) - 1

    def test_reset_repopulates(self, mock):
        for m in mock.fetch_unread():
            mock.archive(m)
        assert mock.fetch_unread() == []
        mock.reset()
        assert len(mock.fetch_unread()) == 6

    def test_state_persists_across_provider_instances(self, mock, temp_env):
        mock.send_reply(mock.fetch_unread()[0], "x")
        # New instance reads the persisted state.
        p2 = MockProvider()
        assert len(p2.fetch_unread()) == 5

    def test_state_file_corruption_recovers_gracefully(self, temp_env):
        """A garbled state file should not crash the provider."""
        state = temp_env / "data" / "mock_state.json"
        state.parent.mkdir(exist_ok=True)
        state.write_text("{not json}", encoding="utf-8")
        p = MockProvider()
        # Should still serve the full seed (treats corrupt state as empty).
        assert len(p.fetch_unread()) == 6


class TestFetchById:
    def test_fetch_existing_ids(self, mock):
        out = mock.fetch_by_ids(["m1", "m3"])
        assert sorted(m.id for m in out) == ["m1", "m3"]

    def test_fetch_missing_id_skipped_silently(self, mock):
        out = mock.fetch_by_ids(["m1", "nonexistent", "m2"])
        assert sorted(m.id for m in out) == ["m1", "m2"]

    def test_fetch_empty_list_returns_empty(self, mock):
        assert mock.fetch_by_ids([]) == []


class TestActionApi:
    def test_send_reply_records_event(self, mock):
        target = mock.fetch_unread()[0]
        msg = mock.send_reply(target, "hello")
        assert target.sender_email in msg
        assert "sent" in msg.lower() or "[mock]" in msg

    def test_create_draft_records_event(self, mock):
        target = mock.fetch_unread()[0]
        msg = mock.create_draft(target, "hello")
        assert target.thread_id in msg

    def test_apply_label_records_event(self, mock):
        target = mock.fetch_unread()[0]
        msg = mock.apply_label(target, "Needs review")
        assert "Needs review" in msg
        assert target.id in msg

    def test_archive_records_event(self, mock):
        target = mock.fetch_unread()[0]
        msg = mock.archive(target)
        assert target.id in msg

    def test_health_always_ok(self, mock):
        ok, _ = mock.health()
        assert ok is True
