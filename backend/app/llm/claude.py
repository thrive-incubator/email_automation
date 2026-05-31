import json
import re
from functools import lru_cache
from pathlib import Path

from ..config import BASE_DIR, get_settings
from ..providers.base import EmailMessage
from ..schemas import Rule
from .base import Answerer

_SKILL_PATH = BASE_DIR / "skills" / "humanizer" / "SKILL.md"
# Strip residual markdown bold (**x**) that leaks through and renders as literal
# asterisks in Gmail's plain-text view. Underscores are too risky to strip
# blindly (they appear in URLs/IDs); we instruct the model not to use them.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)

# Collapse a single mid-paragraph \n into a space. LLMs habitually hard-wrap at
# ~70 chars (a convention from training data); Gmail renders each \n as a visible
# break, making paragraphs look like terminal output. Two cases we deliberately
# do NOT collapse:
#   - \n\n  → paragraph break (handled by negative lookahead)
#   - ,\n   → sign-off pattern ("Best,\nShai"); handled by negative lookbehind
_PARAGRAPH_WRAP_RE = re.compile(r"(?<![,\n])\n(?!\n)")


@lru_cache(maxsize=1)
def _humanizer_skill() -> str:
    return _SKILL_PATH.read_text(encoding="utf-8") if _SKILL_PATH.exists() else ""


def _scrub_markdown(text: str) -> str:
    """Belt-and-suspenders: remove **bold** markers regardless of what the LLM did."""
    return _BOLD_RE.sub(r"\1", text)


def _unwrap_paragraphs(text: str) -> str:
    """Collapse mid-paragraph LLM hard-wraps. Preserves paragraph breaks (blank
    lines) and sign-off line breaks (the \\n right after 'Best,', 'Warmly,', etc.)."""
    return _PARAGRAPH_WRAP_RE.sub(" ", text)


def _reply_prompt(
    email: EmailMessage, rule: Rule, voice: str, knowledge: str, guardrails: str
) -> str:
    thread = "\n".join(email.thread_context) if email.thread_context else "(none)"
    # Per-rule drafting instructions take precedence; they're the rule author's
    # specific guidance about what to include / avoid / route / word-count.
    rule_specific = (
        f"\n\nRULE-SPECIFIC INSTRUCTIONS (highest priority — follow these exactly):\n"
        f"{rule.reply_prompt}"
        if rule.reply_prompt
        else ""
    )
    return f"""Draft a reply to the email below on behalf of the inbox owner.

VOICE / TONE TO USE:
{voice or "(no specific voice provided — be warm, concise, and professional)"}

GUARDRAILS (must follow):
{guardrails or "(none)"}

KNOWLEDGE BASE (answer ONLY from this; if it doesn't contain the answer, say so plainly
and keep the reply short rather than inventing details):
{knowledge or "(no knowledge provided)"}

RULE CONTEXT: {rule.name} — {rule.description}{rule_specific}

PRIOR THREAD:
{thread}

EMAIL TO REPLY TO:
From: {email.sender} <{email.sender_email}>
Subject: {email.subject}
Body:
{email.body}

Write ONLY the reply body text — no subject line, no "Draft:" prefix, no markdown
code fences. Sign off appropriately for the voice. If you cannot answer confidently
from the knowledge base, write a brief holding reply that does not promise specifics.

FORMATTING RULES (this goes into a plain-text Gmail message):
- No markdown formatting of any kind. No **bold**, no *italics*, no _underscores_,
  no #headers, no `backticks`, no markdown links like [text](url). Use plain text
  only — markdown markers render literally in Gmail and look broken.
- For emphasis, rephrase rather than bolding. We rarely use any emphasis at all.
- Real URLs are fine; just paste them as-is, not wrapped in [].
- DO NOT insert hard line breaks inside a paragraph. Each paragraph is a single
  line of any length; Gmail will wrap it on the recipient's screen automatically.
  Manual wraps every ~70 chars look like 1995 terminal output.
- Use a single blank line between paragraphs. For sign-offs, use a normal line
  break after the comma (e.g. "Best,\\nShai"), not a blank line.
"""


class ClaudeAnswerer(Answerer):
    name = "claude"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def draft_reply(
        self,
        email: EmailMessage,
        rule: Rule,
        voice: str,
        knowledge: str,
        guardrails: str,
    ) -> str:
        """Single Claude call. The humanizer skill is loaded as a cached system
        prompt so the model applies it inline while drafting — no post-edit pass."""
        client = self._get_client()
        skill = _humanizer_skill()
        system_blocks = []
        if skill:
            system_blocks.append(
                {
                    "type": "text",
                    "text": (
                        skill
                        + "\n\n---\n\n## How to apply this skill when drafting\n\n"
                        "The user message will give you a reply to draft. Apply the "
                        "patterns above as you write — do not produce a draft and then "
                        "edit it. Internally, after drafting, ask yourself: 'what about "
                        "this still reads as AI?' and revise before returning."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            )
        msg = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=1200,
            system=system_blocks or None,
            messages=[
                {
                    "role": "user",
                    "content": _reply_prompt(email, rule, voice, knowledge, guardrails),
                }
            ],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        ).strip()
        # Defensive: strip any **bold** markers, then collapse mid-paragraph
        # hard-wraps (LLMs habitually wrap around ~70 chars, which renders as
        # visible line breaks in Gmail).
        return _unwrap_paragraphs(_scrub_markdown(text))

    def summarize_handoff(self, email: EmailMessage, rule: Rule) -> dict:
        client = self._get_client()
        prompt = (
            "Summarize this email as a structured CRM handoff. Return strict JSON with "
            "keys: contact_name, contact_email, intent, suggested_next_step, urgency "
            "(low|medium|high).\n\n"
            f"From: {email.sender} <{email.sender_email}>\nSubject: {email.subject}\n"
            f"Body:\n{email.body}"
        )
        msg = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        ).strip()
        try:
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {
                "contact_name": email.sender,
                "contact_email": email.sender_email,
                "intent": text[:400],
                "suggested_next_step": "Review and follow up.",
                "urgency": "medium",
            }

    def health(self) -> tuple[bool, str]:
        if not self.settings.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not set."
        try:
            client = self._get_client()
            client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, f"Claude OK (model {self.settings.anthropic_model})."
        except Exception as exc:  # noqa: BLE001
            return False, f"Claude error: {exc}"
