"""Regression tests for every bug we already fixed during this build.

Each test below names the bug it pins. If any of them break, we've regressed.
"""
from __future__ import annotations

import pytest


# ── Bug 1: empty knowledge_files leaked the whole knowledge base ────────────--
class TestBrainEmptyListNoLeak:
    """`brain.read_all_knowledge([])` used to return ALL knowledge files because
    `if names else list_knowledge()` treated `[]` as falsy. Fix: distinguish
    None (all) from [] (none)."""

    def test_empty_list_returns_no_knowledge(self, temp_env):
        from app import brain
        (temp_env / "brain" / "knowledge" / "a.md").write_text("LEAK_A", encoding="utf-8")
        (temp_env / "brain" / "knowledge" / "b.md").write_text("LEAK_B", encoding="utf-8")
        out = brain.read_all_knowledge([])
        assert "LEAK_A" not in out
        assert "LEAK_B" not in out
        assert out == ""

    def test_none_still_returns_all(self, temp_env):
        from app import brain
        (temp_env / "brain" / "knowledge" / "a.md").write_text("KEEP_A", encoding="utf-8")
        out = brain.read_all_knowledge(None)
        assert "KEEP_A" in out


# ── Bug 2: module-level DATA_DIR paths captured at import time ──────────────--
class TestLazyDataPaths:
    """`_CRM_OUTBOX = DATA_DIR / "..."` (and the mock provider's _STATE_FILE) were
    captured at import time, so they ignored runtime config changes. All such
    paths must now be looked up lazily."""

    def test_crm_outbox_resolves_against_current_data_dir(self, temp_env):
        from app.executor import _crm_outbox_path
        assert str(temp_env / "data") in str(_crm_outbox_path())

    def test_mock_state_file_resolves_against_current_data_dir(self, temp_env):
        from app.providers.mock import _state_file
        assert str(temp_env / "data") in str(_state_file())

    def test_rules_file_resolves_against_current_config(self, temp_env):
        from app import config
        from app import rules as rules_store
        rules_store.list_rules()  # triggers a write of defaults
        assert (config.RULES_FILE).exists()
        assert str(temp_env / "rules.json") == str(config.RULES_FILE)


# ── Bug 3: markdown bold leaks into Gmail as literal ** ─────────────────────--
class TestNoMarkdownBoldInDrafts:
    def test_double_asterisk_stripped_from_claude_output(self):
        from app.llm.claude import _scrub_markdown
        out = _scrub_markdown("Program is **fully virtual** today.")
        assert "**" not in out
        assert "fully virtual" in out

    def test_underscores_preserved(self):
        from app.llm.claude import _scrub_markdown
        # Underscores belong in URLs and IDs — we tell the model not to use them
        # as italic markers but DO NOT strip them blindly.
        assert _scrub_markdown("see _README_ and a_b.md") == "see _README_ and a_b.md"


# ── Bug 4: LLMs hard-wrap at ~70 chars, rendering as line breaks in Gmail ────-
class TestParagraphUnwrap:
    def test_screenshot_bug_paragraph_collapses_to_one_line(self):
        from app.llm.claude import _unwrap_paragraphs
        raw = (
            "Cost: the June 2026 founding cohort is $2,500.\n"
            "Cohorts after that run $3,000. The June price is a bit lower because\n"
            "it's our inaugural run."
        )
        fixed = _unwrap_paragraphs(raw)
        assert "\n" not in fixed
        assert "$2,500." in fixed and "$3,000." in fixed

    def test_signoff_break_preserved(self):
        from app.llm.claude import _unwrap_paragraphs
        assert _unwrap_paragraphs("Body.\n\nBest,\nShai") == "Body.\n\nBest,\nShai"

    def test_paragraph_break_preserved(self):
        from app.llm.claude import _unwrap_paragraphs
        assert _unwrap_paragraphs("A.\n\nB.") == "A.\n\nB."


# ── Bug 5: exclude action used to do nothing / went through LLM anyway ───────-
class TestExcludeShortCircuits:
    """Excluded emails must create a Decision with status='excluded', NO draft,
    and the LLM must never be called."""

    def test_exclude_skips_llm_and_sets_excluded_status(
        self, db, seed_brain, seed_rules, monkeypatch
    ):
        from app import engine
        from app.llm.base import Classification
        from app.llm import mock as mock_llm
        from app.models import Decision
        from app.providers import reset_provider, get_provider

        reset_provider()
        get_provider().reset()

        # Patch the filter to deterministically match the exclude rule for m1.
        def _classify(self, email, rules):
            excl = next(r for r in rules if r.action_type == "exclude")
            return Classification(
                matched_rule_id=excl.id, confidence=0.95,
                safety_flag=True, sales_opportunity=False,
                summary="legal stuff", reasoning="x",
            )

        monkeypatch.setattr(mock_llm.MockFilter, "classify", _classify)

        # Track whether the answerer was called.
        answer_count = {"n": 0}
        orig = mock_llm.MockAnswerer.draft_reply
        def _draft(self, *a, **kw):
            answer_count["n"] += 1
            return orig(self, *a, **kw)
        monkeypatch.setattr(mock_llm.MockAnswerer, "draft_reply", _draft)

        engine.run_pipeline(db, limit=50, waiting_on_me=False)
        excluded = db.query(Decision).filter_by(action_type="exclude").all()
        assert len(excluded) == 6  # every email matches the rule under the stub
        for d in excluded:
            assert d.status == "excluded"
            assert d.proposed_draft == ""
        assert answer_count["n"] == 0, "answerer must not be called for exclude"


# ── Bug 6: sales_opportunity used to downgrade reply rules to flag ──────────--
class TestSalesOpportunityDoesNotOverrideReply:
    """Removed because Shai's ruleset has explicit partnership/enrollee rules now."""

    def test_reply_with_sales_signal_still_replies(self):
        from app.engine import _resolve_action
        from app.llm.base import Classification
        from app.schemas import Rule

        rule = Rule(id="r1", name="x", filter_prompt="x", action_type="reply")
        cls = Classification(
            matched_rule_id="r1", confidence=0.95,
            safety_flag=False, sales_opportunity=True,
            summary="", reasoning="",
        )
        assert _resolve_action(cls, rule) == "reply"


# ── Bug 7: reply_prompt empty marker would prime model with blank block ─────--
class TestReplyPromptBlockOnlyWhenSet:
    def test_no_rule_specific_header_when_unset(self):
        from app.llm.claude import _reply_prompt
        from app.providers.base import EmailMessage
        from app.schemas import Rule

        rule = Rule(
            id="r", name="r", filter_prompt="x", action_type="reply",
            reply_prompt=None,
        )
        email = EmailMessage(
            id="m", thread_id="t", sender="x", sender_email="x@x.com",
            subject="s", snippet="", body="b",
        )
        out = _reply_prompt(email, rule, "voice", "knowledge", "guardrails")
        assert "RULE-SPECIFIC INSTRUCTIONS" not in out

    def test_header_present_when_reply_prompt_set(self):
        from app.llm.claude import _reply_prompt
        from app.providers.base import EmailMessage
        from app.schemas import Rule

        rule = Rule(
            id="r", name="r", filter_prompt="x", action_type="reply",
            reply_prompt="Always be brief.",
        )
        email = EmailMessage(
            id="m", thread_id="t", sender="x", sender_email="x@x.com",
            subject="s", snippet="", body="b",
        )
        out = _reply_prompt(email, rule, "voice", "knowledge", "guardrails")
        assert "RULE-SPECIFIC INSTRUCTIONS" in out
        assert "Always be brief." in out
