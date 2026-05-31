from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Decision(Base):
    """A proposed action for one email, awaiting human review."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)

    # Source email
    email_id: Mapped[str] = mapped_column(String, index=True)
    thread_id: Mapped[str] = mapped_column(String, index=True)
    sender: Mapped[str] = mapped_column(String)
    sender_email: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    snippet: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[str] = mapped_column(String, default="")

    # Classification (Gemini)
    matched_rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_rule_name: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    safety_flag: Mapped[bool] = mapped_column(default=False)
    sales_opportunity: Mapped[bool] = mapped_column(default=False)
    reasoning: Mapped[str] = mapped_column(Text, default="")

    # Resolved action
    action_type: Mapped[str] = mapped_column(String, default="flag")
    send_mode: Mapped[str] = mapped_column(String, default="draft")  # draft | send
    summary: Mapped[str] = mapped_column(Text, default="")
    proposed_draft: Mapped[str] = mapped_column(Text, default="")
    voice_used: Mapped[str | None] = mapped_column(String, nullable=True)
    knowledge_refs: Mapped[list] = mapped_column(JSON, default=list)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    handoff_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending | submitted | discarded | failed
    user_edited_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProcessedEmail(Base):
    """Dedupe ledger so re-running the pipeline never double-handles an email."""

    __tablename__ = "processed_emails"

    email_id: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String, index=True)
    event: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
