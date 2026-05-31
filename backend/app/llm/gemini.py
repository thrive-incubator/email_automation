import json

import httpx

from ..config import get_settings
from ..providers.base import EmailMessage
from ..schemas import Rule
from .base import Classification, Filter, build_classification_prompt

_API = "https://generativelanguage.googleapis.com/v1beta/models"

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "matched_rule_id": {"type": "STRING", "nullable": True},
        "confidence": {"type": "NUMBER"},
        "safety_flag": {"type": "BOOLEAN"},
        "sales_opportunity": {"type": "BOOLEAN"},
        "summary": {"type": "STRING"},
        "reasoning": {"type": "STRING"},
    },
    "required": ["confidence", "safety_flag", "sales_opportunity", "summary", "reasoning"],
}


class GeminiFilter(Filter):
    name = "gemini"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _generate(self, prompt: str) -> dict:
        s = self.settings
        url = f"{_API}/{s.gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
                "temperature": 0.1,
            },
        }
        resp = httpx.post(
            url,
            params={"key": s.gemini_api_key},
            json=payload,
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    def classify(self, email: EmailMessage, rules: list[Rule]) -> Classification:
        prompt = build_classification_prompt(email, rules)
        try:
            raw = self._generate(prompt)
        except Exception as exc:  # noqa: BLE001 — degrade safely to a human flag
            return Classification(
                matched_rule_id=None,
                confidence=0.0,
                safety_flag=True,
                sales_opportunity=False,
                summary="Classifier error — needs human review.",
                reasoning=f"Gemini call failed: {exc}",
            )
        rid = raw.get("matched_rule_id")
        return Classification(
            matched_rule_id=rid or None,
            confidence=float(raw.get("confidence", 0.0)),
            safety_flag=bool(raw.get("safety_flag", False)),
            sales_opportunity=bool(raw.get("sales_opportunity", False)),
            summary=raw.get("summary", ""),
            reasoning=raw.get("reasoning", ""),
        )

    def health(self) -> tuple[bool, str]:
        if not self.settings.gemini_api_key:
            return False, "GEMINI_API_KEY not set."
        try:
            url = f"{_API}/{self.settings.gemini_model}:generateContent"
            resp = httpx.post(
                url,
                params={"key": self.settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": "ping"}]}]},
                timeout=20,
            )
            if resp.status_code == 200:
                return True, f"Gemini OK (model {self.settings.gemini_model})."
            return False, f"Gemini {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Gemini error: {exc}"
