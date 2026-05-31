from fastapi import APIRouter, HTTPException

from .. import rules as rules_store
from ..schemas import Rule, RuleCreate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[Rule])
def list_rules() -> list[Rule]:
    return rules_store.list_rules()


@router.post("", response_model=Rule)
def create_rule(data: RuleCreate) -> Rule:
    return rules_store.create_rule(data)


@router.put("/{rule_id}", response_model=Rule)
def update_rule(rule_id: str, data: RuleCreate) -> Rule:
    updated = rules_store.update_rule(rule_id, data)
    if not updated:
        raise HTTPException(404, "Rule not found")
    return updated


@router.delete("/{rule_id}")
def delete_rule(rule_id: str) -> dict:
    if not rules_store.delete_rule(rule_id):
        raise HTTPException(404, "Rule not found")
    return {"ok": True}
