from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..providers.base import EmailMessage
from ..schemas import Rule


@dataclass
class Classification:
    matched_rule_id: str | None
    confidence: float  # 0..1
    safety_flag: bool
    sales_opportunity: bool
    summary: str
    reasoning: str


class Filter(ABC):
    """Stage 1: decide which rule (if any) an email matches, with confidence."""

    name: str = "filter"

    @abstractmethod
    def classify(self, email: EmailMessage, rules: list[Rule]) -> Classification: ...

    @abstractmethod
    def health(self) -> tuple[bool, str]: ...


class Answerer(ABC):
    """Stage 2: draft a reply using the matched rule's voice + knowledge."""

    name: str = "answerer"

    @abstractmethod
    def draft_reply(
        self,
        email: EmailMessage,
        rule: Rule,
        voice: str,
        knowledge: str,
        guardrails: str,
    ) -> str: ...

    @abstractmethod
    def summarize_handoff(self, email: EmailMessage, rule: Rule) -> dict: ...

    @abstractmethod
    def health(self) -> tuple[bool, str]: ...


def build_classification_prompt(email: EmailMessage, rules: list[Rule]) -> str:
    rule_block = "\n".join(
        f"- id: {r.id}\n  name: {r.name}\n  when_to_match: {r.filter_prompt}"
        for r in rules
        if r.enabled
    )
    return f"""You are an email triage classifier for a busy founder's inbox.
Decide which ONE rule best matches the email below, or none.

RULES:
{rule_block}

EMAIL:
From: {email.sender} <{email.sender_email}>
Subject: {email.subject}
Body:
{email.body}

Return strict JSON with keys:
- matched_rule_id: the id of the best-matching rule, or null if none match
- confidence: number 0..1, how sure you are the rule matches AND a safe action is clear
- safety_flag: true if the email involves legal threats, complaints, safety/privacy
  issues, anything sensitive, or anything where an automated reply could cause harm
- sales_opportunity: true if this looks like a sales/partnership/pricing opportunity
- summary: one short sentence describing what the sender wants
- reasoning: one short sentence on why you chose this rule and confidence
"""
