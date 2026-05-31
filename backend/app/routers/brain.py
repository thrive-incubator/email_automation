from fastapi import APIRouter, HTTPException

from .. import brain
from ..schemas import BrainFile, BrainFileUpdate

router = APIRouter(prefix="/api/brain", tags=["brain"])


@router.get("")
def list_brain() -> dict:
    return {
        "voices": brain.list_voices(),
        "knowledge": brain.list_knowledge(),
        "guardrails": ["guardrails.md"],
    }


@router.get("/{kind}/{name}", response_model=BrainFile)
def get_brain_file(kind: str, name: str) -> BrainFile:
    try:
        content = brain.get_file(kind, name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return BrainFile(kind=kind, name=name, content=content)


@router.put("/{kind}/{name}", response_model=BrainFile)
def update_brain_file(kind: str, name: str, body: BrainFileUpdate) -> BrainFile:
    try:
        brain.write_file(kind, name, body.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return BrainFile(kind=kind, name=name, content=body.content)
