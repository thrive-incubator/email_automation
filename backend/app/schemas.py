from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "reply", "flag", "discard", "label", "crm_handoff", "exclude"
]
SendMode = Literal["draft", "send"]


# ── Rules ───────────────────────────────────────────────────────────────────
class Rule(BaseModel):
    id: str
    name: str
    description: str = ""
    filter_prompt: str
    action_type: ActionType = "reply"
    voice_file: str | None = None
    knowledge_files: list[str] = Field(default_factory=list)
    reply_prompt: str | None = None  # per-rule fine-grained drafting instructions
    confidence_threshold: float = 0.85
    send_mode: SendMode = "draft"
    label: str | None = None
    enabled: bool = True
    priority: int = 100


class RuleCreate(BaseModel):
    name: str
    description: str = ""
    filter_prompt: str
    action_type: ActionType = "reply"
    voice_file: str | None = None
    knowledge_files: list[str] = Field(default_factory=list)
    reply_prompt: str | None = None
    confidence_threshold: float = 0.85
    send_mode: SendMode = "draft"
    label: str | None = None
    enabled: bool = True
    priority: int = 100


# ── Decisions ─────────────────────────────────────────────────────────────--
class DecisionOut(BaseModel):
    id: str
    email_id: str
    thread_id: str
    sender: str
    sender_email: str
    subject: str
    snippet: str
    body: str
    received_at: str
    matched_rule_id: str | None
    matched_rule_name: str | None
    confidence: float
    safety_flag: bool
    sales_opportunity: bool
    reasoning: str
    action_type: str
    send_mode: str
    summary: str
    proposed_draft: str
    voice_used: str | None
    knowledge_refs: list
    label: str | None
    handoff_payload: dict | None
    status: str
    user_edited_draft: str | None
    execution_result: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    fetched: int
    new: int
    skipped: int
    decisions: list[DecisionOut]


class SubmitItem(BaseModel):
    decision_id: str
    edited_draft: str | None = None
    save_to_knowledge: str | None = None  # knowledge filename to append correction


class SubmitRequest(BaseModel):
    items: list[SubmitItem]


class SubmitResult(BaseModel):
    decision_id: str
    ok: bool
    message: str


# ── Brain ─────────────────────────────────────────────────────────────────--
class BrainFile(BaseModel):
    kind: Literal["voice", "knowledge", "guardrails"]
    name: str
    content: str


class BrainFileUpdate(BaseModel):
    content: str


# ── Settings / health ─────────────────────────────────────────────────────--
class ProviderStatus(BaseModel):
    name: str
    configured: bool
    ok: bool
    detail: str


class InboxItem(BaseModel):
    id: str
    thread_id: str
    sender: str
    sender_email: str
    subject: str
    snippet: str
    body: str
    received_at: str
    processed: bool  # already pushed through the pipeline
    decision_id: str | None


class SettingsOut(BaseModel):
    email_provider: str
    gemini_model: str
    anthropic_model: str
    gmail_connected: bool
    crm_handoff_target: str
