"""In-memory inbox seeded with realistic emails so the whole app runs with zero setup.

State (read/replied/labeled/archived) lives in process memory + a JSON file so the
review flow behaves believably across page reloads during local testing.
"""

import json
from datetime import datetime, timedelta, timezone

from .. import config
from .base import EmailMessage, EmailProvider


def _state_file():
    """Resolve the persistence path lazily so it picks up DATA_DIR overrides."""
    return config.DATA_DIR / "mock_state.json"


def _seed() -> list[EmailMessage]:
    now = datetime.now(timezone.utc)

    def ts(mins: int = 0, days: int = 0) -> str:
        return (now - timedelta(minutes=mins, days=days)).isoformat()

    return [
        EmailMessage(
            id="m1",
            thread_id="t1",
            sender="Bob Henderson",
            sender_email="bob.henderson@example.org",
            subject="Re: Thanks for joining the March webinar",
            snippet="My certificate doesn't show how long I attended...",
            body=(
                "Hi, thanks for the certificate! But it doesn't say how many hours "
                "I attended. My PD coordinator needs the hours listed. Can you add "
                "that the session was 1 hour to my certificate? Thanks, Bob"
            ),
            received_at=ts(mins=15),
        ),
        EmailMessage(
            id="m2",
            thread_id="t2",
            sender="Maria Gomez",
            sender_email="mgomez@headstart-wa.org",
            subject="Slides from last month's session",
            snippet="Could you send me the slides from the February webinar?",
            body=(
                "Hello! I missed grabbing the slides from the February webinar and a "
                "colleague asked for them. Could you share the slide deck and the "
                "recording link? Much appreciated. — Maria"
            ),
            received_at=ts(mins=120),
        ),
        EmailMessage(
            id="m3",
            thread_id="t3",
            sender="Dana Whitfield",
            sender_email="dwhitfield@ccrr-county.gov",
            subject="W-9 needed for our finance team",
            snippet="Our finance team needs a current W-9 before they can process...",
            body=(
                "Hi there, before our finance department can pay the invoice they need "
                "a current W-9 on file. Could you send that over? Thank you, Dana"
            ),
            received_at=ts(days=1),
        ),
        EmailMessage(
            id="m4",
            thread_id="t4",
            sender="Terrence Cole",
            sender_email="tcole@districthealth.org",
            subject="Move our participant + invoice date",
            snippet="We need to move Bob to the October cohort and change our invoice...",
            body=(
                "Two things: (1) please move our participant Bob Reyes from the "
                "Wednesday 3pm slot to the October cohort, and (2) our fiscal year "
                "starts in July so we need the invoice dated July 1. Thanks!"
            ),
            received_at=ts(days=3),
        ),
        EmailMessage(
            id="m5",
            thread_id="t5",
            sender="Priya Nair",
            sender_email="pnair@earlyintervention.org",
            subject="Loved the webinar — can you tell me more about the program?",
            snippet="This was exactly what our state needs. Can we set up a call to...",
            body=(
                "That webinar was fantastic and exactly what our early intervention "
                "team has been looking for. Can you tell me more about how the program "
                "works and what pricing looks like for a statewide rollout? Would love "
                "to set up a call. — Priya"
            ),
            received_at=ts(days=8),
        ),
        EmailMessage(
            id="m6",
            thread_id="t6",
            sender="Greg Tomlin",
            sender_email="gtomlin@example.com",
            subject="URGENT: legal threat re: data",
            snippet="Our attorney has concerns about how attendee data is stored...",
            body=(
                "Our attorney has raised concerns about how you are storing attendee "
                "data and is considering legal action. Please explain your data "
                "retention and deletion policy immediately."
            ),
            received_at=ts(days=20),
        ),
    ]


class MockProvider(EmailProvider):
    name = "mock"

    def __init__(self) -> None:
        self._messages = {m.id: m for m in _seed()}
        self._state = self._load_state()

    def _load_state(self) -> dict:
        path = _state_file()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"handled": [], "log": []}

    def _save_state(self) -> None:
        path = _state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _record(self, email_id: str, event: str) -> None:
        self._state["log"].append(
            {"email_id": email_id, "event": event, "at": datetime.now(timezone.utc).isoformat()}
        )
        if email_id not in self._state["handled"]:
            self._state["handled"].append(email_id)
        self._save_state()

    def fetch_unread(
        self,
        limit: int = 50,
        since_days: int | None = None,
        waiting_on_me: bool = True,
    ) -> list[EmailMessage]:
        # No threads in the mock inbox, so waiting_on_me is a no-op here.
        del waiting_on_me
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=since_days)
            if since_days is not None
            else None
        )

        def fresh_enough(m: EmailMessage) -> bool:
            if cutoff is None or not m.received_at:
                return True
            try:
                return datetime.fromisoformat(m.received_at) >= cutoff
            except ValueError:
                return True

        return [
            m
            for m in self._messages.values()
            if m.id not in self._state["handled"] and fresh_enough(m)
        ][:limit]

    def fetch_by_ids(self, ids: list[str]) -> list[EmailMessage]:
        return [self._messages[i] for i in ids if i in self._messages]

    def send_reply(self, msg: EmailMessage, body: str) -> str:
        self._record(msg.id, "sent")
        return f"[mock] Sent reply to {msg.sender_email} in thread {msg.thread_id}."

    def create_draft(self, msg: EmailMessage, body: str) -> str:
        self._record(msg.id, "drafted")
        return f"[mock] Draft created for {msg.sender_email} in thread {msg.thread_id}."

    def apply_label(self, msg: EmailMessage, label: str) -> str:
        self._record(msg.id, f"labeled:{label}")
        return f"[mock] Applied label '{label}' to message {msg.id}."

    def archive(self, msg: EmailMessage) -> str:
        self._record(msg.id, "archived")
        return f"[mock] Archived message {msg.id}."

    def health(self) -> tuple[bool, str]:
        return True, "Mock provider ready (seeded sample inbox)."

    # Test helper: forget all handled state so the demo inbox refills.
    def reset(self) -> None:
        self._state = {"handled": [], "log": []}
        self._save_state()
