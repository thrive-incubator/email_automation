import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import engine
from ..db import get_db
from ..executor import execute_decision
from ..models import Decision, ProcessedEmail
from ..providers import get_provider
from ..schemas import (
    DecisionOut,
    InboxItem,
    RunResponse,
    SubmitRequest,
    SubmitResult,
)

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/inbox", response_model=list[InboxItem])
def inbox(
    limit: int = 50,
    since_days: int | None = None,
    waiting_on_me: bool = True,
    db: Session = Depends(get_db),
) -> list[InboxItem]:
    """Cheap read-only view of unread emails. NO LLM is invoked.

    Annotates each email with whether the pipeline has already processed it
    (and the resulting decision id) so the UI can hide / link those.
    """
    provider = get_provider()
    emails = provider.fetch_unread(
        limit=limit, since_days=since_days, waiting_on_me=waiting_on_me
    )
    if not emails:
        return []
    decisions = (
        db.query(Decision).filter(Decision.email_id.in_([e.id for e in emails])).all()
    )
    decision_by_email = {d.email_id: d.id for d in decisions}
    return [
        InboxItem(
            id=e.id,
            thread_id=e.thread_id,
            sender=e.sender,
            sender_email=e.sender_email,
            subject=e.subject,
            snippet=e.snippet,
            body=e.body,
            received_at=e.received_at,
            processed=e.id in decision_by_email,
            decision_id=decision_by_email.get(e.id),
        )
        for e in emails
    ]


@router.post("/run", response_model=RunResponse)
def run(
    limit: int = 50,
    since_days: int | None = None,
    waiting_on_me: bool = True,
    db: Session = Depends(get_db),
) -> RunResponse:
    result = engine.run_pipeline(
        db, limit=limit, since_days=since_days, waiting_on_me=waiting_on_me
    )
    return RunResponse(
        fetched=result["fetched"],
        new=result["new"],
        skipped=result["skipped"],
        decisions=[DecisionOut.model_validate(d) for d in result["decisions"]],
    )


@router.get("/run/stream")
def run_stream(
    limit: int = 50,
    since_days: int | None = None,
    waiting_on_me: bool = True,
    email_ids: str | None = None,  # comma-separated for EventSource (GET) compat
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Server-sent events form so the UI can show a real progress bar.

    Emits SSE events: `start`, `progress`, `decision`, `done`.
    """

    ids = [i for i in (email_ids or "").split(",") if i]

    def event_stream():
        for event in engine.iter_pipeline(
            db,
            limit=limit,
            since_days=since_days,
            waiting_on_me=waiting_on_me,
            email_ids=ids or None,
        ):
            kind = event.pop("type")
            if "decision" in event:
                event["decision"] = DecisionOut.model_validate(event["decision"]).model_dump(mode="json")
            yield f"event: {kind}\ndata: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    status: str | None = None, db: Session = Depends(get_db)
) -> list[DecisionOut]:
    q = db.query(Decision)
    if status:
        q = q.filter(Decision.status == status)
    rows = q.order_by(Decision.created_at.desc()).all()
    return [DecisionOut.model_validate(d) for d in rows]


@router.post("/decisions/submit", response_model=list[SubmitResult])
def submit(req: SubmitRequest, db: Session = Depends(get_db)) -> list[SubmitResult]:
    results: list[SubmitResult] = []
    for item in req.items:
        decision = db.get(Decision, item.decision_id)
        if not decision:
            results.append(
                SubmitResult(decision_id=item.decision_id, ok=False, message="Not found")
            )
            continue
        ok, message = execute_decision(
            db,
            decision,
            edited_draft=item.edited_draft,
            save_to_knowledge=item.save_to_knowledge,
        )
        results.append(SubmitResult(decision_id=item.decision_id, ok=ok, message=message))
    return results


@router.post("/decisions/{decision_id}/discard", response_model=SubmitResult)
def discard(decision_id: str, db: Session = Depends(get_db)) -> SubmitResult:
    decision = db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(404, "Decision not found")
    decision.status = "discarded"
    db.commit()
    return SubmitResult(decision_id=decision_id, ok=True, message="Discarded")


@router.post("/reset")
def reset(db: Session = Depends(get_db)) -> dict:
    """Clear all decisions + dedupe ledger; refill the mock inbox if in mock mode."""
    db.query(Decision).delete()
    db.query(ProcessedEmail).delete()
    db.commit()
    provider = get_provider()
    if hasattr(provider, "reset"):
        provider.reset()
    return {"ok": True}
