"""GeminiFilter via respx-mocked httpx — no real Google API calls."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx
import pytest
import respx

from app.llm.gemini import GeminiFilter
from app.providers.base import EmailMessage
from app.schemas import Rule


def _email():
    return EmailMessage(
        id="m1", thread_id="t1", sender="X", sender_email="x@x.com",
        subject="Test", snippet="", body="Body",
    )


def _rule():
    return Rule(
        id="r1", name="Rule 1", description="", filter_prompt="match anything",
        action_type="reply", priority=10,
    )


def _gemini_response(payload: dict) -> dict:
    """Shape a Gemini-API-compatible response wrapping our JSON payload as text."""
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload)}]}}
        ]
    }


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    from app import config
    config.get_settings.cache_clear()


class TestClassify:
    @respx.mock
    def test_happy_path_parses_json_response(self, with_key):
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_gemini_response({
                    "matched_rule_id": "r1",
                    "confidence": 0.92,
                    "safety_flag": False,
                    "sales_opportunity": False,
                    "summary": "Routine question",
                    "reasoning": "Keyword overlap",
                }),
            )
        )
        out = GeminiFilter().classify(_email(), [_rule()])
        assert out.matched_rule_id == "r1"
        assert out.confidence == pytest.approx(0.92)
        assert out.safety_flag is False
        assert out.summary == "Routine question"

    @respx.mock
    def test_http_error_degrades_to_safe_flag(self, with_key):
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(return_value=httpx.Response(500, text="boom"))
        out = GeminiFilter().classify(_email(), [_rule()])
        # Must not raise; must return safe defaults: no match, safety_flag=True.
        assert out.matched_rule_id is None
        assert out.confidence == 0.0
        assert out.safety_flag is True
        assert "failed" in out.reasoning.lower()

    @respx.mock
    def test_malformed_json_degrades_to_safe_flag(self, with_key):
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "not json!"}]}}]},
            )
        )
        out = GeminiFilter().classify(_email(), [_rule()])
        assert out.matched_rule_id is None
        assert out.safety_flag is True

    @respx.mock
    def test_request_contains_api_key_and_response_schema(self, with_key):
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_gemini_response({
                    "matched_rule_id": None,
                    "confidence": 0.0,
                    "safety_flag": False,
                    "sales_opportunity": False,
                    "summary": "x",
                    "reasoning": "x",
                }),
            )
        )
        GeminiFilter().classify(_email(), [_rule()])
        assert route.called
        req = route.calls.last.request
        # Key is in query string.
        assert "key=test-key" in str(req.url)
        body = json.loads(req.content)
        # Response schema enforced + temperature low for determinism.
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["temperature"] <= 0.2


class TestHealth:
    def test_no_key_reports_disconnected(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from app import config
        config.get_settings.cache_clear()
        ok, detail = GeminiFilter().health()
        assert not ok
        assert "not set" in detail.lower()

    @respx.mock
    def test_with_key_pings_endpoint(self, with_key):
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(return_value=httpx.Response(200, json={"candidates": []}))
        ok, detail = GeminiFilter().health()
        assert ok
        assert "gemini-test" in detail
        assert route.called

    @respx.mock
    def test_with_key_but_bad_response_reports_failure(self, with_key):
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        ).mock(return_value=httpx.Response(404, text="model not found"))
        ok, detail = GeminiFilter().health()
        assert not ok
        assert "404" in detail
