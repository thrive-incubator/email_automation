"""Shared fixtures for the whole test suite.

Design notes (the "QA lead's" call):
- Every test gets an isolated filesystem (temp BASE_DIR, brain/, rules.json, data/).
- The provider/llm singletons are reset between tests so module state never leaks.
- External APIs (Anthropic, Gemini, Gmail) are NEVER called — they are mocked at the
  client boundary. A separate `live` marker is reserved for opt-in smoke tests.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ── Isolated config / paths ─────────────────────────────────────────────────--
@pytest.fixture
def temp_base(tmp_path, monkeypatch):
    """Redirect BASE_DIR + BRAIN_DIR + RULES_FILE + DATA_DIR to a temp tree.

    Also resets the cached settings/provider singletons so each test sees fresh state.
    """
    base = tmp_path / "backend"
    (base / "brain" / "voices").mkdir(parents=True)
    (base / "brain" / "knowledge").mkdir(parents=True)
    (base / "data").mkdir(parents=True)

    # Copy the humanizer SKILL.md if present so the answerer can load it; tests
    # that need a different one can overwrite.
    src_skill = Path(__file__).resolve().parent.parent / "skills" / "humanizer" / "SKILL.md"
    if src_skill.exists():
        (base / "skills" / "humanizer").mkdir(parents=True)
        shutil.copy(src_skill, base / "skills" / "humanizer" / "SKILL.md")

    from app import config
    monkeypatch.setattr(config, "BASE_DIR", base)
    monkeypatch.setattr(config, "BRAIN_DIR", base / "brain")
    monkeypatch.setattr(config, "RULES_FILE", base / "rules.json")
    monkeypatch.setattr(config, "DATA_DIR", base / "data")
    config.get_settings.cache_clear()

    # Brain module re-imports the path constants; patch them too.
    from app import brain
    monkeypatch.setattr(brain, "VOICES_DIR", base / "brain" / "voices")
    monkeypatch.setattr(brain, "KNOWLEDGE_DIR", base / "brain" / "knowledge")
    monkeypatch.setattr(brain, "GUARDRAILS_FILE", base / "brain" / "guardrails.md")

    # Reset the lazy provider singleton.
    from app import providers
    providers.reset_provider()

    # Clear the humanizer skill cache (the test base may have a different path).
    from app.llm import claude as claude_mod
    monkeypatch.setattr(claude_mod, "_SKILL_PATH", base / "skills" / "humanizer" / "SKILL.md")
    claude_mod._humanizer_skill.cache_clear()

    yield base

    # Teardown: reset singletons so module state doesn't leak.
    config.get_settings.cache_clear()
    providers.reset_provider()
    claude_mod._humanizer_skill.cache_clear()


@pytest.fixture
def temp_env(temp_base, monkeypatch):
    """Force mock provider + no LLM keys → reproducible local-only behavior."""
    monkeypatch.setenv("EMAIL_PROVIDER", "mock")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CRM_WEBHOOK_URL", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{temp_base}/data/test.db")
    # Re-read settings now that env is patched.
    from app import config
    config.get_settings.cache_clear()
    return temp_base


# ── Brain & rules seeding helpers ────────────────────────────────────────────-
@pytest.fixture
def seed_brain(temp_env):
    """Minimal brain content so reply rules have something to draw from."""
    (temp_env / "brain" / "guardrails.md").write_text(
        "Never invent facts. Be brief.", encoding="utf-8"
    )
    (temp_env / "brain" / "voices" / "warm.md").write_text(
        "Warm, concise, sign off as Test.", encoding="utf-8"
    )
    (temp_env / "brain" / "knowledge" / "faq.md").write_text(
        "# FAQ\n\n## Q: Sample\n\nSample answer.\n", encoding="utf-8"
    )
    return temp_env


@pytest.fixture
def seed_rules(temp_env):
    """A representative ruleset covering every action_type."""
    from app.schemas import Rule
    rules = [
        Rule(
            id="phishing-flag",
            name="Phishing guard",
            description="Catch suspicious mail.",
            filter_prompt="Match if phishing/spoof signals: login portal, urgent verify, credentials.",
            action_type="flag",
            label="Security review",
            priority=1,
        ),
        Rule(
            id="excluded-skip",
            name="Excluded categories",
            description="Legal/finance/IP — skip entirely.",
            filter_prompt="Match if from legal counsel, finance, IP, investors, recruiters.",
            action_type="exclude",
            priority=2,
        ),
        Rule(
            id="reply-billing",
            name="Billing question",
            description="Route invoice/W9/payment questions.",
            filter_prompt="Match if asking about invoice, W9, payment, billing, or tax-exempt forms.",
            action_type="reply",
            voice_file="warm.md",
            knowledge_files=["faq.md"],
            reply_prompt="Keep under 100 words. Always route to billing@example.com.",
            send_mode="draft",
            priority=10,
        ),
        Rule(
            id="reply-send",
            name="Quick reply",
            description="Always-send reply.",
            filter_prompt="Match generic friendly hello messages.",
            action_type="reply",
            voice_file="warm.md",
            knowledge_files=["faq.md"],
            send_mode="send",
            priority=20,
        ),
        Rule(
            id="label-internal",
            name="Internal mail",
            description="Label internal mail.",
            filter_prompt="Match internal staff messages.",
            action_type="label",
            label="Internal",
            priority=30,
        ),
        Rule(
            id="discard-promo",
            name="Discard promos",
            description="Auto-archive promos.",
            filter_prompt="Match promotional newsletters.",
            action_type="discard",
            priority=40,
        ),
        Rule(
            id="crm-leads",
            name="CRM handoff",
            description="Push leads to CRM.",
            filter_prompt="Match sales-qualified leads.",
            action_type="crm_handoff",
            label="Lead",
            priority=50,
        ),
    ]
    from app.config import RULES_FILE
    RULES_FILE.write_text(
        json.dumps([r.model_dump() for r in rules], indent=2), encoding="utf-8"
    )
    return rules


# ── Database ────────────────────────────────────────────────────────────────-
@pytest.fixture
def db(temp_env):
    """Fresh in-memory-ish SQLite for each test."""
    from app.db import Base, engine as prod_engine
    from app import db as db_mod

    test_engine = create_engine(
        f"sqlite:///{temp_env}/data/test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.drop_all(bind=prod_engine)  # belt-and-suspenders for shared engine
    Base.metadata.create_all(bind=test_engine)
    db_mod.engine = test_engine
    db_mod.SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    session = db_mod.SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


# ── HTTP client ─────────────────────────────────────────────────────────────-
@pytest.fixture
def client(db, seed_brain, seed_rules):
    """FastAPI test client wired to a fresh app + the test DB session."""
    from app.main import app
    from app.db import get_db

    def _override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── LLM mocks (boundary mocks; never reach the network) ─────────────────────--
@pytest.fixture
def stub_anthropic(monkeypatch):
    """Patch the Anthropic client so ClaudeAnswerer returns a deterministic draft."""
    from app.llm import claude as claude_mod

    fake_client = MagicMock()

    def _create(**kwargs):
        # Echo back a recognisable draft. Tests can inspect the actual prompt.
        m = MagicMock()
        m.content = [MagicMock(type="text", text="Hi there,\n\nThanks for your note.\n\nBest,\nTest")]
        return m

    fake_client.messages.create = MagicMock(side_effect=_create)

    def _get_client(self):
        return fake_client

    monkeypatch.setattr(claude_mod.ClaudeAnswerer, "_get_client", _get_client)
    # Force the answerer factory to use the real Claude client (not the mock answerer
    # selected when key is missing).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app import config
    config.get_settings.cache_clear()
    return fake_client


@pytest.fixture
def stub_gemini(monkeypatch):
    """Patch the Gemini classifier to a deterministic mock returning a fixed result."""
    from app.llm import gemini as gemini_mod
    from app.llm.base import Classification

    captured = {"calls": []}

    def _classify(self, email, rules):
        captured["calls"].append({"email_id": email.id, "rule_count": len(rules)})
        # Choose the first enabled rule with action_type == "reply"; else first enabled.
        chosen = next((r for r in rules if r.enabled and r.action_type == "reply"), None)
        if chosen is None:
            chosen = next((r for r in rules if r.enabled), None)
        return Classification(
            matched_rule_id=chosen.id if chosen else None,
            confidence=0.95,
            safety_flag=False,
            sales_opportunity=False,
            summary="test classification",
            reasoning="stub gemini",
        )

    monkeypatch.setattr(gemini_mod.GeminiFilter, "classify", _classify)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app import config
    config.get_settings.cache_clear()
    return captured
