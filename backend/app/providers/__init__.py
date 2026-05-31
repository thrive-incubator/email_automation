from ..config import get_settings
from .base import EmailMessage, EmailProvider
from .mock import MockProvider

_provider: EmailProvider | None = None


def get_provider() -> EmailProvider:
    global _provider
    settings = get_settings()
    if _provider is not None:
        return _provider
    if settings.email_provider == "gmail":
        from .gmail import GmailProvider

        _provider = GmailProvider()
    else:
        _provider = MockProvider()
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None


__all__ = ["EmailMessage", "EmailProvider", "get_provider", "reset_provider"]
