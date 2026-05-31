from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    sender: str  # display name
    sender_email: str
    subject: str
    snippet: str
    body: str
    received_at: str = ""
    thread_context: list[str] = field(default_factory=list)  # prior messages in thread
    rfc822_message_id: str = ""  # Message-ID header, for In-Reply-To when replying
    to_header: str = ""  # original To, used to set the reply From/Reply-To


class EmailProvider(ABC):
    """Abstraction over an inbox. Mock and Gmail both implement this."""

    name: str = "base"

    @abstractmethod
    def fetch_unread(
        self,
        limit: int = 50,
        since_days: int | None = None,
        waiting_on_me: bool = True,
    ) -> list[EmailMessage]:
        """Return unread inbound messages, optionally filtered to "waiting on me".

        waiting_on_me=True (default) skips any thread where the last message was
        sent by the connected account — i.e. you already replied last and nothing's
        come back. Set False to include those too.
        """

    @abstractmethod
    def fetch_by_ids(self, ids: list[str]) -> list[EmailMessage]:
        """Fetch specific messages by id — used to process a user-selected subset."""

    @abstractmethod
    def send_reply(self, msg: EmailMessage, body: str) -> str:
        """Send a reply in-thread. Returns a human-readable result."""

    @abstractmethod
    def create_draft(self, msg: EmailMessage, body: str) -> str:
        """Create a draft reply in-thread (not sent). Returns a result string."""

    @abstractmethod
    def apply_label(self, msg: EmailMessage, label: str) -> str: ...

    @abstractmethod
    def archive(self, msg: EmailMessage) -> str:
        """Archive / mark handled."""

    @abstractmethod
    def health(self) -> tuple[bool, str]:
        """(ok, detail) — is this provider ready to use?"""
