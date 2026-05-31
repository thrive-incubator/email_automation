from fastapi import APIRouter

from ..config import get_settings
from ..llm import get_answerer, get_filter
from ..providers import get_provider
from ..schemas import ProviderStatus, SettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings_view() -> SettingsOut:
    s = get_settings()
    provider = get_provider()
    gmail_connected = getattr(provider, "is_connected", lambda: False)()
    return SettingsOut(
        email_provider=s.email_provider,
        gemini_model=s.gemini_model,
        anthropic_model=s.anthropic_model,
        gmail_connected=gmail_connected,
        crm_handoff_target=s.crm_webhook_url or "local file (data/crm_outbox.jsonl)",
    )


@router.post("/test", response_model=list[ProviderStatus])
def test_connections() -> list[ProviderStatus]:
    s = get_settings()
    statuses: list[ProviderStatus] = []

    filt = get_filter()
    ok, detail = filt.health()
    statuses.append(
        ProviderStatus(name=f"Filter ({filt.name})", configured=bool(s.gemini_api_key), ok=ok, detail=detail)
    )

    ans = get_answerer()
    ok, detail = ans.health()
    statuses.append(
        ProviderStatus(name=f"Answerer ({ans.name})", configured=bool(s.anthropic_api_key), ok=ok, detail=detail)
    )

    provider = get_provider()
    ok, detail = provider.health()
    statuses.append(
        ProviderStatus(name=f"Email ({provider.name})", configured=True, ok=ok, detail=detail)
    )
    return statuses
