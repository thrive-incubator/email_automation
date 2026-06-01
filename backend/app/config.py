from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  (parent of app/)
BASE_DIR = Path(__file__).resolve().parent.parent
BRAIN_DIR = BASE_DIR / "brain"
RULES_FILE = BASE_DIR / "rules.json"
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Models
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Email provider
    email_provider: str = "mock"  # "mock" | "gmail"
    gmail_client_secret_file: str = "./data/client_secret.json"
    gmail_token_file: str = "./data/gmail_token.json"
    gmail_sender: str = ""

    # CRM handoff
    crm_webhook_url: str = ""

    # App
    database_url: str = "sqlite:///./data/app.db"
    frontend_origin: str = "http://localhost:5180"

    def resolve(self, p: str) -> Path:
        """Resolve a possibly-relative config path against the backend dir."""
        path = Path(p)
        return path if path.is_absolute() else (BASE_DIR / path)


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
