"""MockFilter + MockAnswerer behavior (zero-key local pipeline)."""
from __future__ import annotations

from app.llm.mock import MockAnswerer, MockFilter
from app.providers.base import EmailMessage
from app.schemas import Rule


def _email(subject="x", body="x", sender_email="x@x.com", sender="Sender"):
    return EmailMessage(
        id="m1", thread_id="t1", sender=sender, sender_email=sender_email,
        subject=subject, snippet=body[:80], body=body,
    )


def _rule(name, filter_prompt, action="reply", threshold=0.85, label=None):
    return Rule(
        id=name.lower().replace(" ", "-"),
        name=name,
        description="",
        filter_prompt=filter_prompt,
        action_type=action,
        confidence_threshold=threshold,
        priority=10,
        label=label,
    )


class TestMockFilter:
    def setup_method(self):
        self.f = MockFilter()

    def test_keyword_overlap_picks_best_rule(self):
        rules = [
            _rule("Billing", "invoice w9 payment finance tax-exempt billing"),
            _rule("Webinar", "certificate recording attendance webinar slides"),
        ]
        out = self.f.classify(
            _email(subject="W9 invoice payment", body="Can you send an invoice and W9 for tax-exempt finance?"),
            rules,
        )
        assert out.matched_rule_id == "billing"
        assert out.confidence >= 0.7  # 3+ keyword overlap → confident

    def test_returns_no_match_when_no_overlap(self):
        rules = [_rule("Billing", "invoice w9 finance")]
        out = self.f.classify(
            _email(subject="Hello", body="Greetings, friend."),
            rules,
        )
        assert out.matched_rule_id is None
        assert out.confidence == 0.0

    def test_safety_keywords_set_safety_flag(self):
        rules = [_rule("Anything", "general")]
        out = self.f.classify(
            _email(body="Our attorney is preparing a lawsuit about privacy."),
            rules,
        )
        assert out.safety_flag is True
        # Safety caps confidence to 0.4.
        assert out.confidence <= 0.4

    def test_sales_keywords_set_sales_flag(self):
        rules = [_rule("Enrollee", "enroll pricing more about call demo interested")]
        out = self.f.classify(
            _email(body="I want to learn more about pricing and a demo call."),
            rules,
        )
        assert out.sales_opportunity is True

    def test_flag_rule_wins_when_sales_present(self):
        """Sales-style flag rules get a boost so they outrank reply rules."""
        rules = [
            _rule("Reply rule", "general greeting", action="reply"),
            _rule("Sales flag", "interested pricing call demo", action="flag"),
        ]
        out = self.f.classify(
            _email(body="Interested in pricing, can we schedule a call?"),
            rules,
        )
        assert out.matched_rule_id == "sales-flag"

    def test_disabled_rules_ignored(self):
        billing = _rule("Billing", "invoice w9 finance")
        disabled = _rule("Webinar", "certificate")
        disabled.enabled = False
        out = self.f.classify(_email(body="Need W9 invoice"), [billing, disabled])
        assert out.matched_rule_id == "billing"

    def test_health_always_ok(self):
        ok, _ = self.f.health()
        assert ok is True


class TestMockAnswerer:
    def setup_method(self):
        self.a = MockAnswerer()

    def test_draft_contains_first_name_and_signoff(self):
        rule = _rule("Reply", "x")
        draft = self.a.draft_reply(
            _email(sender="Alice Tester"), rule, voice="", knowledge="", guardrails=""
        )
        assert "Hi Alice," in draft
        assert "Best,\nThe Team" in draft

    def test_pulls_from_first_qa_section_in_knowledge(self):
        rule = _rule("Reply", "x")
        knowledge = (
            "# Header\n\n"
            "Top-of-file instructions that should NOT appear in the draft.\n\n"
            "## Q: What is the price?\n\n"
            "The price is $2,500 for the founding cohort.\n\n"
            "## Q: Another\n\n"
            "Other answer.\n"
        )
        draft = self.a.draft_reply(
            _email(), rule, voice="", knowledge=knowledge, guardrails=""
        )
        assert "The price is $2,500" in draft
        # Doesn't leak the header instructions or the second Q&A.
        assert "Top-of-file instructions" not in draft
        assert "Other answer" not in draft

    def test_strips_markdown_bold_from_snippet(self):
        rule = _rule("Reply", "x")
        knowledge = "## Q: A\n\nThe program is **fully virtual** today.\n"
        draft = self.a.draft_reply(_email(), rule, voice="", knowledge=knowledge, guardrails="")
        assert "**" not in draft

    def test_collapses_hard_wraps_in_snippet(self):
        rule = _rule("Reply", "x")
        knowledge = "## Q: A\n\nOne sentence here.\nA second sentence on a new line.\n"
        draft = self.a.draft_reply(_email(), rule, voice="", knowledge=knowledge, guardrails="")
        assert "One sentence here. A second sentence on a new line." in draft

    def test_summarize_handoff_returns_structured_dict(self):
        rule = _rule("Lead", "x", action="crm_handoff")
        out = self.a.summarize_handoff(_email(sender="Bob", sender_email="b@b.com"), rule)
        assert out["contact_email"] == "b@b.com"
        assert "urgency" in out
        assert out["urgency"] in ("low", "medium", "high")
