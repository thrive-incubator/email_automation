"""Exhaustive matrix for `engine._resolve_action`.

This function is the policy heart of the whole pipeline — every guardrail (safety,
confidence, exclude precedence) flows through here. We test every combination.
"""
from __future__ import annotations

import pytest

from app.engine import _resolve_action
from app.llm.base import Classification
from app.schemas import Rule


def _rule(action: str, threshold: float = 0.85) -> Rule:
    return Rule(
        id=f"r-{action}",
        name=f"rule-{action}",
        description="",
        filter_prompt="x",
        action_type=action,
        confidence_threshold=threshold,
        priority=10,
    )


def _cls(
    confidence: float = 0.95,
    safety: bool = False,
    sales: bool = False,
    matched_id: str | None = "r-reply",
) -> Classification:
    return Classification(
        matched_rule_id=matched_id,
        confidence=confidence,
        safety_flag=safety,
        sales_opportunity=sales,
        summary="x",
        reasoning="x",
    )


class TestNoRuleMatched:
    def test_no_rule_returns_flag(self):
        assert _resolve_action(_cls(), None) == "flag"


class TestConfidenceGate:
    """Below the rule's threshold → flag, regardless of action_type."""

    @pytest.mark.parametrize("action", ["reply", "label", "discard", "crm_handoff", "exclude"])
    def test_low_confidence_demotes_any_action_to_flag(self, action):
        rule = _rule(action, threshold=0.85)
        out = _resolve_action(_cls(confidence=0.5), rule)
        assert out == "flag"

    @pytest.mark.parametrize("action", ["reply", "label", "discard", "crm_handoff"])
    def test_at_threshold_passes(self, action):
        rule = _rule(action, threshold=0.85)
        # Confidence == threshold is OK (it's a `<` check, not `<=`).
        assert _resolve_action(_cls(confidence=0.85), rule) == action


class TestExcludePrecedence:
    """Exclude rules win over safety/sales/normal signals at confidence >= threshold."""

    def test_exclude_beats_safety_flag(self):
        """Legal mail often trips safety; that's exactly why Shai wants exclude."""
        rule = _rule("exclude")
        out = _resolve_action(_cls(confidence=0.95, safety=True), rule)
        assert out == "exclude"

    def test_exclude_beats_sales_opportunity(self):
        rule = _rule("exclude")
        out = _resolve_action(_cls(confidence=0.95, sales=True), rule)
        assert out == "exclude"

    def test_exclude_still_gated_by_confidence(self):
        """Wrongly classifying as exclude is worse than over-flagging."""
        rule = _rule("exclude", threshold=0.85)
        out = _resolve_action(_cls(confidence=0.6), rule)
        assert out == "flag"


class TestSafetyGuardrail:
    """Safety flag demotes any non-exclude action to flag for human review."""

    @pytest.mark.parametrize(
        "action", ["reply", "label", "discard", "crm_handoff"]
    )
    def test_safety_overrides_non_exclude(self, action):
        rule = _rule(action)
        out = _resolve_action(_cls(confidence=0.95, safety=True), rule)
        assert out == "flag"

    def test_safety_on_flag_rule_stays_flag(self):
        rule = _rule("flag")
        out = _resolve_action(_cls(confidence=0.95, safety=True), rule)
        assert out == "flag"


class TestSalesOpportunity:
    """We deliberately DO NOT downgrade reply rules on sales_opportunity any more —
    Shai's ruleset has explicit partnership/enrollee rules; the sales flag is just
    a UI hint now. Pin that."""

    @pytest.mark.parametrize("action", ["reply", "label", "discard", "crm_handoff"])
    def test_sales_opportunity_does_not_change_action(self, action):
        rule = _rule(action)
        out = _resolve_action(_cls(confidence=0.95, sales=True), rule)
        assert out == action

    def test_sales_opportunity_does_not_block_exclude(self):
        rule = _rule("exclude")
        out = _resolve_action(_cls(confidence=0.95, sales=True), rule)
        assert out == "exclude"


class TestHappyPaths:
    @pytest.mark.parametrize(
        "action", ["reply", "flag", "label", "discard", "crm_handoff", "exclude"]
    )
    def test_clean_signal_returns_rule_action(self, action):
        rule = _rule(action)
        assert _resolve_action(_cls(confidence=0.95), rule) == action
