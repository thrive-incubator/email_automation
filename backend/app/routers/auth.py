"""Gmail OAuth (test-mode) connect flow.

The redirect URI used here — http://localhost:8008/api/auth/gmail/callback — must be
added as an Authorized redirect URI on the OAuth client in Google Cloud Console.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..config import get_settings
from ..providers import get_provider

router = APIRouter(prefix="/api/auth/gmail", tags=["auth"])

REDIRECT_PATH = "/api/auth/gmail/callback"


def _gmail_provider():
    provider = get_provider()
    if provider.name != "gmail":
        raise HTTPException(
            400,
            "EMAIL_PROVIDER is not 'gmail'. Set EMAIL_PROVIDER=gmail in .env to connect.",
        )
    return provider


@router.get("/start")
def start(request: Request) -> dict:
    provider = _gmail_provider()
    redirect_uri = str(request.base_url).rstrip("/") + REDIRECT_PATH
    flow = provider.build_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return {"auth_url": auth_url}


@router.get("/callback")
def callback(request: Request, code: str | None = None) -> RedirectResponse:
    provider = _gmail_provider()
    if not code:
        raise HTTPException(400, "Missing authorization code.")
    redirect_uri = str(request.base_url).rstrip("/") + REDIRECT_PATH
    flow = provider.build_flow(redirect_uri)
    flow.fetch_token(code=code)
    provider.save_token(flow.credentials)
    frontend = get_settings().frontend_origin
    return RedirectResponse(url=f"{frontend}/settings?gmail=connected")
