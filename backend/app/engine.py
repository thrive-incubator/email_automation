"""The pipeline: pull unread → classify (Gemini) → resolve action → draft (Claude)."""

import uuid
from collections.abc import Iterator

from sqlalchemy.orm import Session

from . import brain
from .llm import Classification, get_answerer, get_filter
from .models import Decision, ProcessedEmail
from .providers import get_provider
from .providers.base import EmailMessage
from .rules import get_rule, list_rules


def _resolve_action(cls: Classification, rule) -> str:
    """Decide the final action, applying guardrails over the rule's default."""
    if rule is None:
        return "flag"
    # Low confidence always escalates to human review — including "exclude".
    # (If the classifier isn't sure, don't silently skip something that might
    # have needed a reply.)
    if cls.confidence < rule.confidence_threshold:
        return "flag"
    # "exclude" wins over the safety/sales guardrails: legal/finance/IP mail
    # often trips safety signals — that's precisely why it's on the exclude list.
    if rule.action_type == "exclude":
        return "exclude"
    # Safety always wins → human review (kept: this is a backstop for the case
    # where the matched rule didn't contemplate a safety/legal/privacy signal).
    if cls.safety_flag:
        return "flag"
    # The `sales_opportunity` signal is still collected and shown in the UI as a
    # hint, but it no longer overrides the rule's action — Shai's ruleset has
    # explicit rules for partnership/applicant (3) and prospective enrollee (8),
    # so we trust those over a generic "smells sales" heuristic.
    return rule.action_type


def _build_decision(db: Session, email: EmailMessage) -> Decision:
    rules = list_rules()
    cls = get_filter().classify(email, rules)
    rule = get_rule(cls.matched_rule_id) if cls.matched_rule_id else None
    action = _resolve_action(cls, rule)

    proposed_draft = ""
    voice_used = None
    knowledge_refs: list[str] = []
    handoff_payload = None
    label = rule.label if rule else "Needs Review"

    # "exclude" is auto-final: no LLM call, no Gmail action; just record it.
    if action == "exclude":
        decision = Decision(
            id=f"d-{uuid.uuid4().hex[:10]}",
            email_id=email.id,
            thread_id=email.thread_id,
            sender=email.sender,
            sender_email=email.sender_email,
            subject=email.subject,
            snippet=email.snippet,
            body=email.body,
            received_at=email.received_at,
            matched_rule_id=rule.id if rule else None,
            matched_rule_name=rule.name if rule else None,
            confidence=cls.confidence,
            safety_flag=cls.safety_flag,
            sales_opportunity=cls.sales_opportunity,
            reasoning=cls.reasoning,
            action_type="exclude",
            send_mode="draft",
            summary=f"Excluded ({rule.name if rule else 'no rule'}) — left untouched in inbox.",
            status="excluded",
        )
        db.add(decision)
        db.add(ProcessedEmail(email_id=email.id))
        return decision

    if action == "reply" and rule is not None:
        voice_used = rule.voice_file
        knowledge_refs = rule.knowledge_files
        proposed_draft = get_answerer().draft_reply(
            email=email,
            rule=rule,
            voice=brain.read_voice(rule.voice_file) if rule.voice_file else "",
            knowledge=brain.read_all_knowledge(rule.knowledge_files),
            guardrails=brain.read_guardrails(),
        )
    elif action == "crm_handoff" and rule is not None:
        handoff_payload = get_answerer().summarize_handoff(email, rule)

    summary = cls.summary or (rule.name if rule else "No matching rule")
    if action == "flag":
        why = []
        if cls.safety_flag:
            why.append("safety/sensitive")
        if rule and cls.confidence < rule.confidence_threshold:
            why.append(f"low confidence ({cls.confidence:.0%})")
        if cls.sales_opportunity:
            why.append("possible sales opportunity")
        if not rule:
            why.append("no rule matched")
        summary = f"Needs review — {', '.join(why) or 'flagged'}: {summary}"

    decision = Decision(
        id=f"d-{uuid.uuid4().hex[:10]}",
        email_id=email.id,
        thread_id=email.thread_id,
        sender=email.sender,
        sender_email=email.sender_email,
        subject=email.subject,
        snippet=email.snippet,
        body=email.body,
        received_at=email.received_at,
        matched_rule_id=rule.id if rule else None,
        matched_rule_name=rule.name if rule else None,
        confidence=cls.confidence,
        safety_flag=cls.safety_flag,
        sales_opportunity=cls.sales_opportunity,
        reasoning=cls.reasoning,
        action_type=action,
        send_mode=rule.send_mode if rule else "draft",
        summary=summary,
        proposed_draft=proposed_draft,
        voice_used=voice_used,
        knowledge_refs=knowledge_refs,
        label=label,
        handoff_payload=handoff_payload,
        status="pending",
    )
    db.add(decision)
    db.add(ProcessedEmail(email_id=email.id))
    return decision


def iter_pipeline(
    db: Session,
    limit: int = 50,
    since_days: int | None = None,
    waiting_on_me: bool = True,
    email_ids: list[str] | None = None,
) -> Iterator[dict]:
    """Generator form: yields one event per stage so the UI can stream real progress.

    Events:
        {"type": "start", "fetched", "skipped", "total"}
        {"type": "progress", "index", "total", "subject", "sender"}   (before processing one)
        {"type": "decision", "index", "total", "decision": <Decision row>}
        {"type": "done", "fetched", "new", "skipped"}
    """
    provider = get_provider()
    if email_ids:
        emails = provider.fetch_by_ids(email_ids)
    else:
        emails = provider.fetch_unread(
            limit=limit, since_days=since_days, waiting_on_me=waiting_on_me
        )
    already = {p.email_id for p in db.query(ProcessedEmail).all()}
    fresh = [e for e in emails if e.id not in already]
    skipped = len(emails) - len(fresh)

    yield {"type": "start", "fetched": len(emails), "skipped": skipped, "total": len(fresh)}

    new_count = 0
    for i, email in enumerate(fresh, start=1):
        yield {
            "type": "progress",
            "index": i,
            "total": len(fresh),
            "subject": email.subject,
            "sender": email.sender,
        }
        decision = _build_decision(db, email)
        db.commit()
        db.refresh(decision)
        new_count += 1
        yield {"type": "decision", "index": i, "total": len(fresh), "decision": decision}

    yield {"type": "done", "fetched": len(emails), "new": new_count, "skipped": skipped}


def run_pipeline(
    db: Session,
    limit: int = 50,
    since_days: int | None = None,
    waiting_on_me: bool = True,
    email_ids: list[str] | None = None,
) -> dict:
    """Non-streaming version (used by /api/run and tests). Drains iter_pipeline."""
    fetched = skipped = new = 0
    decisions: list[Decision] = []
    for event in iter_pipeline(
        db,
        limit=limit,
        since_days=since_days,
        waiting_on_me=waiting_on_me,
        email_ids=email_ids,
    ):
        if event["type"] == "start":
            fetched, skipped = event["fetched"], event["skipped"]
        elif event["type"] == "decision":
            decisions.append(event["decision"])
        elif event["type"] == "done":
            new = event["new"]
    return {"fetched": fetched, "new": new, "skipped": skipped, "decisions": decisions}
