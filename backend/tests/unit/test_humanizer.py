"""Markdown scrub + paragraph unwrap edge cases — the bug we shipped recently."""
from __future__ import annotations

import pytest

from app.llm.claude import _scrub_markdown, _unwrap_paragraphs


class TestScrubMarkdownBold:
    """`**text**` renders as literal asterisks in Gmail plain text; strip it."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Plain text with no markdown.", "Plain text with no markdown."),
            ("The course is **fully virtual** today.", "The course is fully virtual today."),
            ("Two **bold** spans in **one** line.", "Two bold spans in one line."),
            ("**Leading bold** then text.", "Leading bold then text."),
            ("Trailing **bold here**", "Trailing bold here"),
            ("Multi-line **bold\nacross\nlines** stays.", "Multi-line bold\nacross\nlines stays."),
            ("Nothing to strip — single * is left alone.", "Nothing to strip — single * is left alone."),
            ("", ""),
        ],
    )
    def test_strips_double_asterisk_only(self, raw, expected):
        assert _scrub_markdown(raw) == expected

    def test_does_not_strip_underscores(self):
        # Underscores appear in URLs and message IDs; risky to strip blindly.
        assert _scrub_markdown("See _README_ in path /a/b_c.md") == "See _README_ in path /a/b_c.md"

    def test_does_not_corrupt_urls(self):
        url = "https://example.com/some_path-with-stars?q=*"
        assert url in _scrub_markdown(f"Visit {url} now.")


class TestUnwrapParagraphs:
    """Collapse mid-paragraph hard wraps; preserve paragraph + sign-off breaks."""

    def test_the_exact_bug_from_the_screenshot(self):
        """The example the user pointed out: 5-line paragraph that should be 1."""
        raw = (
            "Straight answer on cost: the June 2026 founding cohort is $2,500.\n"
            "Cohorts after that run $3,000. The June price is a bit lower because\n"
            "it's our inaugural run and we're still putting the finishing touches\n"
            "on a few things. There's also a 4-payment installment plan if that\n"
            "makes things easier."
        )
        fixed = _unwrap_paragraphs(raw)
        assert "\n" not in fixed, "paragraph should be one continuous line"
        assert "$2,500." in fixed and "$3,000." in fixed
        # No double-spaces from the join.
        assert "  " not in fixed

    def test_paragraph_breaks_preserved(self):
        raw = "Para one.\n\nPara two.\n\nPara three."
        assert _unwrap_paragraphs(raw) == raw

    def test_signoff_break_preserved(self):
        """`Best,\\nShai` must stay on two lines (preceded by comma)."""
        raw = "Body text.\n\nBest,\nShai"
        assert _unwrap_paragraphs(raw) == raw

    def test_full_email_with_signoff(self):
        raw = (
            "Hi Bob — happy to help.\n\n"
            "Quick answer: the price for the June cohort is $2,500. The price\n"
            "after that is $3,000. There's a 4-payment plan available too.\n\n"
            "Warmly,\nShai"
        )
        fixed = _unwrap_paragraphs(raw)
        # Greeting line preserved (it's a single paragraph already).
        assert fixed.startswith("Hi Bob — happy to help.")
        # Body collapsed to one line.
        assert "$2,500. The price after that is $3,000." in fixed
        # Sign-off preserved.
        assert fixed.endswith("Warmly,\nShai")
        # Paragraph structure intact.
        assert fixed.count("\n\n") == 2

    def test_multiple_signoff_lines(self):
        raw = "Body.\n\nWarmly,\nShai\nThrive Center"
        # All three sign-off lines preserved? Currently only `,\n` is special-cased,
        # so `Shai\nThrive` would collapse. Pin the current behavior so we know
        # if this changes — a multi-line block signature is unusual for our voice.
        fixed = _unwrap_paragraphs(raw)
        assert "Warmly,\nShai" in fixed

    def test_empty_input(self):
        assert _unwrap_paragraphs("") == ""

    def test_idempotent(self):
        raw = "Para one.\n\nPara two.\n\nBest,\nShai"
        assert _unwrap_paragraphs(_unwrap_paragraphs(raw)) == _unwrap_paragraphs(raw)


class TestComposition:
    """`_scrub_markdown` and `_unwrap_paragraphs` must compose cleanly."""

    def test_bold_inside_a_wrapped_paragraph(self):
        raw = (
            "The program is **fully virtual** and runs\n"
            "for 90 minutes weekly.\n\n"
            "Best,\nShai"
        )
        fixed = _unwrap_paragraphs(_scrub_markdown(raw))
        assert "**" not in fixed
        assert "fully virtual" in fixed
        assert "runs for 90 minutes" in fixed
        assert "Best,\nShai" in fixed
