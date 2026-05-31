"""Rule store backed by a human-readable JSON file (git-friendly)."""

import json
import uuid

from . import config
from .schemas import Rule, RuleCreate

DEFAULT_RULES: list[dict] = [
    {
        "id": "webinar-cert-time",
        "name": "Webinar certificate / timing questions",
        "description": "Attendees asking why their certificate doesn't show duration, "
        "asking for a time stamp, or for the recording/slides.",
        "filter_prompt": (
            "Match if the email is from a webinar attendee asking about their "
            "attendance certificate (e.g. why it doesn't show the number of minutes "
            "or hours attended), asking for a time stamp, or requesting the slides or "
            "recording for the session they attended. Do NOT match if they are asking "
            "about pricing, enrolling, or anything that looks like a sales opportunity."
        ),
        "action_type": "reply",
        "voice_file": "warm-professional.md",
        "knowledge_files": ["webinar-faq.md"],
        "confidence_threshold": 0.9,
        "send_mode": "send",
        "label": None,
        "enabled": True,
        "priority": 10,
    },
    {
        "id": "cohort-admin",
        "name": "Cohort admin & billing requests",
        "description": "W-9 requests, billing contact / invoice / PO / address changes, "
        "and participant schedule changes.",
        "filter_prompt": (
            "Match if the email is a cohort administrative request: asking for a W-9, "
            "changing a billing contact, invoice date, billing address, or PO; or a "
            "participant schedule change (moving time slots, replacing or removing a "
            "participant). For W-9 and document requests you may reply directly. For "
            "anything that changes a participant's schedule across systems, prefer to "
            "flag for human review since it requires multi-system updates."
        ),
        "action_type": "reply",
        "voice_file": "warm-professional.md",
        "knowledge_files": ["cohort-admin.md"],
        "confidence_threshold": 0.9,
        "send_mode": "draft",
        "label": None,
        "enabled": True,
        "priority": 20,
    },
    {
        "id": "sales-opportunity",
        "name": "Sales opportunity → flag",
        "description": "Anyone asking to learn more about the program, pricing, "
        "or expressing buying intent. Always surfaced for Shai, never auto-answered.",
        "filter_prompt": (
            "Match if the email expresses interest in learning more about the program, "
            "asks about pricing or enrollment, or otherwise looks like a sales or "
            "partnership opportunity worth a human reply."
        ),
        "action_type": "flag",
        "voice_file": None,
        "knowledge_files": [],
        "confidence_threshold": 0.6,
        "send_mode": "draft",
        "label": "Needs Review",
        "enabled": True,
        "priority": 5,
    },
]


def _read_raw() -> list[dict]:
    if not config.RULES_FILE.exists():
        save_rules([Rule(**r) for r in DEFAULT_RULES])
    return json.loads(config.RULES_FILE.read_text(encoding="utf-8"))


def list_rules() -> list[Rule]:
    rules = [Rule(**r) for r in _read_raw()]
    return sorted(rules, key=lambda r: r.priority)


def get_rule(rule_id: str) -> Rule | None:
    return next((r for r in list_rules() if r.id == rule_id), None)


def save_rules(rules: list[Rule]) -> None:
    config.RULES_FILE.write_text(
        json.dumps([r.model_dump() for r in rules], indent=2), encoding="utf-8"
    )


def create_rule(data: RuleCreate) -> Rule:
    rule = Rule(id=f"rule-{uuid.uuid4().hex[:8]}", **data.model_dump())
    rules = list_rules()
    rules.append(rule)
    save_rules(rules)
    return rule


def update_rule(rule_id: str, data: RuleCreate) -> Rule | None:
    rules = list_rules()
    for i, r in enumerate(rules):
        if r.id == rule_id:
            rules[i] = Rule(id=rule_id, **data.model_dump())
            save_rules(rules)
            return rules[i]
    return None


def delete_rule(rule_id: str) -> bool:
    rules = list_rules()
    remaining = [r for r in rules if r.id != rule_id]
    if len(remaining) == len(rules):
        return False
    save_rules(remaining)
    return True
