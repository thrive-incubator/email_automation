"""Deterministic, keyword-based stand-ins so the full flow is testable with no API keys.

These are intentionally simple: they make the dashboard, review queue, and execution
path fully exercisable offline, then get swapped for real models by setting the keys.
"""

import re

from ..providers.base import EmailMessage
from ..schemas import Rule
from .base import Answerer, Classification, Filter

_STOP = set(
    "the a an and or to of for in on at is are be do does this that your you our we i "
    "if it not no please can could would will may with from about more your re fwd hi "
    "hello thanks thank as so but they them their there here who what when where which".split()
)
_SAFETY = re.compile(
    r"\b(legal|attorney|lawyer|lawsuit|sue|complaint|privacy|gdpr|breach|harass|threat|urgent)\b",
    re.I,
)
_SALES = re.compile(
    r"\b(pricing|price|cost|enroll|enrollment|demo|call|partnership|rollout|more about|interested|proposal)\b",
    re.I,
)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9\-]+", text.lower()) if w not in _STOP and len(w) > 2}


class MockFilter(Filter):
    name = "mock-filter"

    def classify(self, email: EmailMessage, rules: list[Rule]) -> Classification:
        text = f"{email.subject} {email.body}"
        email_tokens = _tokens(text)
        safety = bool(_SAFETY.search(text))
        sales = bool(_SALES.search(text))

        best_rule: Rule | None = None
        best_overlap = 0
        for rule in rules:
            if not rule.enabled:
                continue
            rule_tokens = _tokens(f"{rule.name} {rule.description} {rule.filter_prompt}")
            if not rule_tokens:
                continue
            overlap = len(email_tokens & rule_tokens)
            # A sales-style (flag) rule wins decisively when a sales signal is present.
            if rule.action_type == "flag" and sales:
                overlap += 3
            if overlap > best_overlap:
                best_overlap, best_rule = overlap, rule

        if best_rule is None or best_overlap == 0:
            return Classification(None, 0.0, safety, sales, "No matching rule.", "mock: no overlap")

        # Confidence grows with the number of shared keywords; clear matches clear the bar.
        confidence = min(0.97, 0.55 + 0.12 * best_overlap)
        if safety:
            confidence = min(confidence, 0.4)
        return Classification(
            matched_rule_id=best_rule.id,
            confidence=round(confidence, 2),
            safety_flag=safety,
            sales_opportunity=sales,
            summary=f"Sender's request relates to: {best_rule.name}.",
            reasoning=f"mock keyword match ({best_overlap} shared terms).",
        )

    def health(self) -> tuple[bool, str]:
        return True, "Mock filter active (no GEMINI_API_KEY set)."


class MockAnswerer(Answerer):
    name = "mock-answerer"

    def draft_reply(
        self,
        email: EmailMessage,
        rule: Rule,
        voice: str,
        knowledge: str,
        guardrails: str,
    ) -> str:
        first_name = email.sender.split()[0] if email.sender else "there"
        snippet = ""
        if knowledge and "## Q:" in knowledge:
            # surface the answer beneath the first "## Q:" entry as a stand-in
            after_q = knowledge.split("## Q:", 1)[1]
            lines = after_q.split("\n", 1)
            answer = lines[1] if len(lines) > 1 else ""
            snippet = answer.split("## ")[0].strip()
        # Strip markdown bold (**x**) defensively, matching the real answerer.
        snippet = re.sub(r"\*\*(.+?)\*\*", r"\1", snippet, flags=re.DOTALL)
        # Collapse any mid-paragraph hard-wraps in the knowledge snippet (the
        # Q&A blocks in the brain often have hand-wrapped lines).
        snippet = re.sub(r"(?<![,\n])\n(?!\n)", " ", snippet)
        return (
            f"Hi {first_name},\n\n"
            f"Thanks for reaching out. {snippet or 'Happy to help with this.'}\n\n"
            f"[mock draft — generated without Claude for rule '{rule.name}'. "
            f"Set ANTHROPIC_API_KEY for real drafts and humanizer post-edit.]\n\n"
            f"Best,\nThe Team"
        )

    def summarize_handoff(self, email: EmailMessage, rule: Rule) -> dict:
        return {
            "contact_name": email.sender,
            "contact_email": email.sender_email,
            "intent": email.snippet or email.subject,
            "suggested_next_step": "Reach out to discuss; looks like an opportunity.",
            "urgency": "medium",
        }

    def health(self) -> tuple[bool, str]:
        return True, "Mock answerer active (no ANTHROPIC_API_KEY set)."
