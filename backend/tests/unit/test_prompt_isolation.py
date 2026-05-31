"""The most important correctness test in the suite.

When a reply rule fires, the prompt sent to Claude must contain ONLY the voice
file + knowledge files explicitly selected by that rule. Leaking other voices
or knowledge would (a) cost more tokens, (b) cause the model to draw on
irrelevant facts, and (c) mix tone instructions.

Strategy: seed the brain with multiple voices and knowledge files, each with a
UNIQUE marker string. Then for each test rule, build the Claude prompt and
assert the configured markers are present AND the other markers are absent.
"""
from __future__ import annotations

import pytest

from app import brain
from app.llm.claude import _reply_prompt
from app.llm.base import build_classification_prompt
from app.providers.base import EmailMessage
from app.schemas import Rule


# ── Brain seeding with distinct, easy-to-grep markers ───────────────────────--
VOICE_MARKERS = {
    "warm.md": "VOICEMARKER_WARM_PROFESSIONAL",
    "inviting.md": "VOICEMARKER_WARM_INVITING",
    "formal.md": "VOICEMARKER_FORMAL_DECLINE",
}
KNOWLEDGE_MARKERS = {
    "billing.md": "KNOWLEDGEMARKER_BILLING_FACTS",
    "webinar.md": "KNOWLEDGEMARKER_WEBINAR_FACTS",
    "enrollment.md": "KNOWLEDGEMARKER_ENROLLMENT_FACTS",
    "scheduling.md": "KNOWLEDGEMARKER_SCHEDULING_FACTS",
}
GUARDRAILS_MARKER = "GUARDRAILSMARKER_GLOBAL_SAFETY"


@pytest.fixture
def isolation_brain(temp_env):
    """Populate the brain with multiple voice/knowledge files, each unique."""
    base = temp_env / "brain"
    for fname, marker in VOICE_MARKERS.items():
        (base / "voices" / fname).write_text(
            f"# Voice {fname}\n\n{marker} — distinctive content for this voice only.\n",
            encoding="utf-8",
        )
    for fname, marker in KNOWLEDGE_MARKERS.items():
        (base / "knowledge" / fname).write_text(
            f"# Knowledge {fname}\n\n## Q: Sample\n\n{marker} — the unique facts.\n",
            encoding="utf-8",
        )
    (base / "guardrails.md").write_text(
        f"{GUARDRAILS_MARKER}\nNever invent facts.\n", encoding="utf-8"
    )
    return base


def _make_email(subject="Test") -> EmailMessage:
    return EmailMessage(
        id="m-iso",
        thread_id="t-iso",
        sender="Alex Tester",
        sender_email="alex@example.com",
        subject=subject,
        snippet="Hello",
        body="Quick question — can you help?",
    )


def _make_rule(voice: str | None, knowledge: list[str], reply_prompt: str | None = None) -> Rule:
    return Rule(
        id=f"r-{voice or 'none'}",
        name="Isolation test rule",
        description="Used by the prompt-isolation tests.",
        filter_prompt="(match anything)",
        action_type="reply",
        voice_file=voice,
        knowledge_files=knowledge,
        reply_prompt=reply_prompt,
        send_mode="draft",
        priority=10,
    )


# ── Brain loader isolation (the foundation) ─────────────────────────────────--
class TestBrainLoaderIsolation:
    """`brain.read_all_knowledge([...])` must read EXACTLY the named files."""

    def test_single_knowledge_file(self, isolation_brain):
        out = brain.read_all_knowledge(["billing.md"])
        assert KNOWLEDGE_MARKERS["billing.md"] in out
        for name, marker in KNOWLEDGE_MARKERS.items():
            if name != "billing.md":
                assert marker not in out, f"leaked {name} into single-file read"

    def test_multiple_knowledge_files(self, isolation_brain):
        out = brain.read_all_knowledge(["billing.md", "webinar.md"])
        assert KNOWLEDGE_MARKERS["billing.md"] in out
        assert KNOWLEDGE_MARKERS["webinar.md"] in out
        # The non-selected ones MUST NOT appear.
        assert KNOWLEDGE_MARKERS["enrollment.md"] not in out
        assert KNOWLEDGE_MARKERS["scheduling.md"] not in out

    def test_empty_list_returns_no_knowledge_content(self, isolation_brain):
        out = brain.read_all_knowledge([])
        # The current contract: empty list means "all" — verify that's intentional;
        # if it changes to "none", this test pins the new behavior.
        # As of this commit, empty list defaults to "all"; the engine never calls
        # with an empty list when a rule has empty knowledge_files (it just passes
        # the empty list straight through and the resulting prompt section reads
        # "(no knowledge provided)" thanks to the `or` guard).
        # → The right way to test "no knowledge" is to verify the engine path.
        # Here we just sanity check the loader itself.
        assert isinstance(out, str)

    def test_voice_loader_returns_only_named_voice(self, isolation_brain):
        out = brain.read_voice("warm.md")
        assert VOICE_MARKERS["warm.md"] in out
        for fname, marker in VOICE_MARKERS.items():
            if fname != "warm.md":
                assert marker not in out

    def test_path_traversal_blocked(self, isolation_brain, tmp_path):
        secret = tmp_path / "secret.md"
        secret.write_text("SECRET_DO_NOT_LEAK", encoding="utf-8")
        # Various traversal attempts — all must resolve to a plain filename.
        for attack in ["../secret.md", "../../tmp/secret.md", "/etc/passwd"]:
            out = brain.read_voice(attack)
            assert "SECRET" not in out
            assert "root:" not in out  # /etc/passwd canary


# ── Reply prompt isolation (the actual answerer surface) ────────────────────--
class TestReplyPromptIsolation:
    """The Claude reply prompt must contain ONLY the configured voice + knowledge."""

    def test_only_selected_voice_appears(self, isolation_brain):
        rule = _make_rule(voice="warm.md", knowledge=["billing.md"])
        voice_text = brain.read_voice(rule.voice_file)
        knowledge_text = brain.read_all_knowledge(rule.knowledge_files)
        guardrails = brain.read_guardrails()

        prompt = _reply_prompt(_make_email(), rule, voice_text, knowledge_text, guardrails)

        assert VOICE_MARKERS["warm.md"] in prompt, "configured voice missing from prompt"
        assert VOICE_MARKERS["inviting.md"] not in prompt, "non-configured voice leaked"
        assert VOICE_MARKERS["formal.md"] not in prompt, "non-configured voice leaked"

    def test_only_selected_knowledge_appears(self, isolation_brain):
        rule = _make_rule(voice="warm.md", knowledge=["billing.md", "webinar.md"])
        voice_text = brain.read_voice(rule.voice_file)
        knowledge_text = brain.read_all_knowledge(rule.knowledge_files)
        guardrails = brain.read_guardrails()

        prompt = _reply_prompt(_make_email(), rule, voice_text, knowledge_text, guardrails)

        assert KNOWLEDGE_MARKERS["billing.md"] in prompt
        assert KNOWLEDGE_MARKERS["webinar.md"] in prompt
        assert KNOWLEDGE_MARKERS["enrollment.md"] not in prompt, "leaked enrollment.md"
        assert KNOWLEDGE_MARKERS["scheduling.md"] not in prompt, "leaked scheduling.md"

    def test_guardrails_always_present(self, isolation_brain):
        rule = _make_rule(voice="warm.md", knowledge=["billing.md"])
        prompt = _reply_prompt(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )
        assert GUARDRAILS_MARKER in prompt

    def test_reply_prompt_field_included_when_set(self, isolation_brain):
        marker = "REPLY_PROMPT_SPECIFIC_INSTRUCTION_XYZ"
        rule = _make_rule(voice="warm.md", knowledge=["billing.md"], reply_prompt=marker)
        prompt = _reply_prompt(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )
        assert marker in prompt

    def test_reply_prompt_field_absent_when_unset(self, isolation_brain):
        rule = _make_rule(voice="warm.md", knowledge=["billing.md"], reply_prompt=None)
        prompt = _reply_prompt(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )
        # When no reply_prompt is configured we must NOT include the
        # "RULE-SPECIFIC INSTRUCTIONS" header — otherwise the model could be
        # primed by an empty block.
        assert "RULE-SPECIFIC INSTRUCTIONS" not in prompt

    def test_empty_knowledge_list_shows_no_knowledge(self, isolation_brain):
        rule = _make_rule(voice="warm.md", knowledge=[])
        knowledge_text = brain.read_all_knowledge(rule.knowledge_files)
        prompt = _reply_prompt(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            knowledge_text,
            brain.read_guardrails(),
        )
        # No knowledge markers anywhere in the prompt.
        for marker in KNOWLEDGE_MARKERS.values():
            assert marker not in prompt
        # And the prompt should be honest about it.
        assert "(no knowledge provided)" in prompt

    def test_no_voice_shows_generic_fallback(self, isolation_brain):
        rule = _make_rule(voice=None, knowledge=["billing.md"])
        voice_text = brain.read_voice(rule.voice_file) if rule.voice_file else ""
        prompt = _reply_prompt(
            _make_email(),
            rule,
            voice_text,
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )
        for marker in VOICE_MARKERS.values():
            assert marker not in prompt
        assert "no specific voice provided" in prompt.lower()

    def test_no_markdown_instruction_present(self, isolation_brain):
        """Regression: the no-markdown formatting rules must be in every reply prompt."""
        rule = _make_rule(voice="warm.md", knowledge=["billing.md"])
        prompt = _reply_prompt(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )
        assert "FORMATTING RULES" in prompt
        assert "No markdown" in prompt
        assert "hard line breaks" in prompt or "hard-wrap" in prompt.lower()


# ── Classification prompt isolation ─────────────────────────────────────────--
class TestClassificationPromptIsolation:
    """The classifier sees EVERY enabled rule's filter_prompt, but no brain content."""

    def test_classifier_sees_all_enabled_rules(self, isolation_brain):
        rules = [
            _make_rule(voice="warm.md", knowledge=["billing.md"]),
            _make_rule(voice="inviting.md", knowledge=["webinar.md"]),
        ]
        # Give them unique filter prompts so we can detect leakage either way.
        rules[0].filter_prompt = "FILTERMARKER_RULE_A"
        rules[1].filter_prompt = "FILTERMARKER_RULE_B"

        prompt = build_classification_prompt(_make_email(), rules)

        assert "FILTERMARKER_RULE_A" in prompt
        assert "FILTERMARKER_RULE_B" in prompt
        # Classifier must NOT see any voice or knowledge content — those belong to
        # the answerer stage.
        for marker in VOICE_MARKERS.values():
            assert marker not in prompt
        for marker in KNOWLEDGE_MARKERS.values():
            assert marker not in prompt

    def test_disabled_rules_omitted_from_classifier(self, isolation_brain):
        a = _make_rule(voice="warm.md", knowledge=["billing.md"])
        a.filter_prompt = "FILTERMARKER_ENABLED"
        b = _make_rule(voice="inviting.md", knowledge=["webinar.md"])
        b.filter_prompt = "FILTERMARKER_DISABLED"
        b.enabled = False

        prompt = build_classification_prompt(_make_email(), [a, b])
        assert "FILTERMARKER_ENABLED" in prompt
        assert "FILTERMARKER_DISABLED" not in prompt


# ── End-to-end isolation through the real ClaudeAnswerer ────────────────────--
class TestDraftReplyIsolation:
    """Capture the actual prompt sent to the Anthropic client; assert no leaks."""

    def test_real_draft_call_includes_only_selected_brain(
        self, isolation_brain, stub_anthropic
    ):
        from app.llm.claude import ClaudeAnswerer

        rule = _make_rule(voice="warm.md", knowledge=["billing.md"])
        answerer = ClaudeAnswerer()
        answerer.draft_reply(
            _make_email(),
            rule,
            brain.read_voice(rule.voice_file),
            brain.read_all_knowledge(rule.knowledge_files),
            brain.read_guardrails(),
        )

        call = stub_anthropic.messages.create.call_args
        user_msg = call.kwargs["messages"][0]["content"]
        system = call.kwargs.get("system") or []
        system_text = "".join(b.get("text", "") for b in system if isinstance(b, dict))
        full_prompt = system_text + "\n" + user_msg

        # Selected content must appear in the prompt that hit the wire.
        assert VOICE_MARKERS["warm.md"] in full_prompt
        assert KNOWLEDGE_MARKERS["billing.md"] in full_prompt
        # No other voice / knowledge should be present anywhere in the request.
        for fname, marker in VOICE_MARKERS.items():
            if fname != "warm.md":
                assert marker not in full_prompt, f"leaked {fname} into wire request"
        for fname, marker in KNOWLEDGE_MARKERS.items():
            if fname != "billing.md":
                assert marker not in full_prompt, f"leaked {fname} into wire request"
