"""Execute an approved Decision's action against the email provider / CRM."""

import json
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from . import brain, config
from .config import get_settings
from .models import AuditLog, Decision
from .providers import get_provider
from .providers.base import EmailMessage


def _crm_outbox_path():
    """Resolve the outbox path lazily so it picks up config/test overrides."""
    return config.DATA_DIR / "crm_outbox.jsonl"


def _email_from_decision(d: Decision) -> EmailMessage:
    return EmailMessage(
        id=d.email_id,
        thread_id=d.thread_id,
        sender=d.sender,
        sender_email=d.sender_email,
        subject=d.subject,
        snippet=d.snippet,
        body=d.body,
        received_at=d.received_at,
    )


def _audit(db: Session, decision_id: str, event: str, detail: str = "") -> None:
    db.add(AuditLog(decision_id=decision_id, event=event, detail=detail))


def _crm_handoff(payload: dict) -> str:
    settings = get_settings()
    record = {"at": datetime.now(timezone.utc).isoformat(), **payload}
    if settings.crm_webhook_url:
        resp = httpx.post(settings.crm_webhook_url, json=record, timeout=30)
        resp.raise_for_status()
        return f"Posted CRM handoff to webhook (status {resp.status_code})."
    outbox = _crm_outbox_path()
    outbox.parent.mkdir(parents=True, exist_ok=True)
    with outbox.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return f"Wrote CRM handoff to {outbox.name} (no webhook configured)."


def execute_decision(
    db: Session,
    decision: Decision,
    edited_draft: str | None = None,
    save_to_knowledge: str | None = None,
) -> tuple[bool, str]:
    if decision.status == "submitted":
        return True, "Already submitted."

    provider = get_provider()
    email = _email_from_decision(decision)

    try:
        if decision.action_type == "reply":
            body = edited_draft if edited_draft is not None else decision.proposed_draft
            if not body.strip():
                raise ValueError("Empty reply body.")
            if decision.send_mode == "send":
                result = provider.send_reply(email, body)
            else:
                result = provider.create_draft(email, body)
            if edited_draft is not None:
                decision.user_edited_draft = edited_draft
            # Learning loop: optionally save the (corrected) answer back to the brain.
            if save_to_knowledge:
                brain.append_knowledge(save_to_knowledge, decision.body, body)
                _audit(db, decision.id, "knowledge_saved", save_to_knowledge)

        elif decision.action_type == "label":
            result = provider.apply_label(email, decision.label or "Auto-handled")

        elif decision.action_type == "discard":
            result = provider.archive(email)

        elif decision.action_type == "crm_handoff":
            result = _crm_handoff(decision.handoff_payload or {
                "contact_name": decision.sender,
                "contact_email": decision.sender_email,
                "intent": decision.summary,
            })
            if decision.label:
                provider.apply_label(email, decision.label)

        elif decision.action_type == "flag":
            # Flag = make it visible for human handling; label it, leave it unread.
            result = provider.apply_label(email, decision.label or "Needs Review")

        elif decision.action_type == "exclude":
            # Auto-finalized at creation time; submitting one is a no-op by design.
            result = "Excluded — no Gmail action taken (per rule)."

        else:
            raise ValueError(f"Unknown action: {decision.action_type}")

        decision.status = "submitted"
        decision.execution_result = result
        decision.executed_at = datetime.now(timezone.utc)
        _audit(db, decision.id, f"executed:{decision.action_type}", result)
        db.commit()
        return True, result

    except Exception as exc:  # noqa: BLE001
        decision.status = "failed"
        decision.execution_result = str(exc)
        _audit(db, decision.id, "failed", str(exc))
        db.commit()
        return False, str(exc)
