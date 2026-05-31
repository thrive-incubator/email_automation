"""Brain CRUD + edge cases beyond the prompt-isolation tests."""
from __future__ import annotations

import pytest

from app import brain


class TestListing:
    def test_lists_voices_sorted(self, temp_env):
        for n in ["zebra.md", "alpha.md", "middle.md"]:
            (temp_env / "brain" / "voices" / n).write_text("x", encoding="utf-8")
        assert brain.list_voices() == ["alpha.md", "middle.md", "zebra.md"]

    def test_lists_knowledge_sorted(self, temp_env):
        for n in ["b.md", "a.md", "c.md"]:
            (temp_env / "brain" / "knowledge" / n).write_text("x", encoding="utf-8")
        assert brain.list_knowledge() == ["a.md", "b.md", "c.md"]

    def test_ignores_non_markdown(self, temp_env):
        (temp_env / "brain" / "voices" / "ok.md").write_text("x", encoding="utf-8")
        (temp_env / "brain" / "voices" / "ignore.txt").write_text("x", encoding="utf-8")
        (temp_env / "brain" / "voices" / "README").write_text("x", encoding="utf-8")
        assert brain.list_voices() == ["ok.md"]

    def test_handles_empty_dirs(self, temp_env):
        assert brain.list_voices() == []
        assert brain.list_knowledge() == []


class TestRead:
    def test_read_voice_returns_content(self, temp_env):
        (temp_env / "brain" / "voices" / "warm.md").write_text("warm voice", encoding="utf-8")
        assert brain.read_voice("warm.md") == "warm voice"

    def test_read_voice_without_extension_auto_adds_md(self, temp_env):
        (temp_env / "brain" / "voices" / "warm.md").write_text("warm voice", encoding="utf-8")
        assert brain.read_voice("warm") == "warm voice"

    def test_read_missing_voice_returns_empty(self, temp_env):
        assert brain.read_voice("never.md") == ""

    def test_read_guardrails(self, temp_env):
        (temp_env / "brain" / "guardrails.md").write_text("never invent.", encoding="utf-8")
        assert brain.read_guardrails() == "never invent."

    def test_read_guardrails_missing_returns_empty(self, temp_env):
        assert brain.read_guardrails() == ""


class TestReadAllKnowledge:
    def test_none_returns_all_files(self, temp_env):
        (temp_env / "brain" / "knowledge" / "a.md").write_text("AAA", encoding="utf-8")
        (temp_env / "brain" / "knowledge" / "b.md").write_text("BBB", encoding="utf-8")
        out = brain.read_all_knowledge(None)
        assert "AAA" in out and "BBB" in out

    def test_empty_list_returns_empty_string(self, temp_env):
        (temp_env / "brain" / "knowledge" / "a.md").write_text("AAA", encoding="utf-8")
        # Regression: must NOT return all files when given empty list.
        assert brain.read_all_knowledge([]) == ""

    def test_named_list_returns_only_named(self, temp_env):
        (temp_env / "brain" / "knowledge" / "a.md").write_text("AAA", encoding="utf-8")
        (temp_env / "brain" / "knowledge" / "b.md").write_text("BBB", encoding="utf-8")
        out = brain.read_all_knowledge(["a.md"])
        assert "AAA" in out
        assert "BBB" not in out

    def test_missing_file_skipped_silently(self, temp_env):
        (temp_env / "brain" / "knowledge" / "a.md").write_text("AAA", encoding="utf-8")
        out = brain.read_all_knowledge(["a.md", "missing.md"])
        assert "AAA" in out

    def test_separator_between_files(self, temp_env):
        (temp_env / "brain" / "knowledge" / "a.md").write_text("AAA", encoding="utf-8")
        (temp_env / "brain" / "knowledge" / "b.md").write_text("BBB", encoding="utf-8")
        out = brain.read_all_knowledge(["a.md", "b.md"])
        assert "---" in out


class TestWrite:
    def test_write_voice_creates_file(self, temp_env):
        brain.write_file("voice", "new.md", "new voice content")
        assert (temp_env / "brain" / "voices" / "new.md").read_text() == "new voice content"

    def test_write_knowledge_creates_file(self, temp_env):
        brain.write_file("knowledge", "new.md", "facts")
        assert (temp_env / "brain" / "knowledge" / "new.md").read_text() == "facts"

    def test_write_guardrails(self, temp_env):
        brain.write_file("guardrails", "guardrails.md", "be safe")
        assert (temp_env / "brain" / "guardrails.md").read_text() == "be safe"

    def test_write_unknown_kind_raises(self, temp_env):
        with pytest.raises(ValueError):
            brain.write_file("nonsense", "x.md", "y")

    def test_write_overwrites_existing(self, temp_env):
        brain.write_file("voice", "x.md", "first")
        brain.write_file("voice", "x.md", "second")
        assert brain.read_voice("x.md") == "second"


class TestAppendKnowledge:
    def test_appends_qa_pair(self, temp_env):
        brain.write_file("knowledge", "faq.md", "# FAQ\n")
        brain.append_knowledge("faq.md", "What is X?", "X is a thing.")
        content = brain.read_knowledge("faq.md")
        assert "## Q: What is X?" in content
        assert "X is a thing." in content
        assert "# FAQ" in content  # original preserved

    def test_appends_to_nonexistent_file_creates_it(self, temp_env):
        brain.append_knowledge("brand-new.md", "Q1", "A1")
        content = brain.read_knowledge("brand-new.md")
        assert "Q1" in content and "A1" in content


class TestPathTraversalDefense:
    """Untrusted filenames must never escape the brain directory."""

    @pytest.mark.parametrize(
        "attack",
        [
            "../../../etc/passwd",
            "../voices/x.md",
            "/tmp/anywhere.md",
            "../../app/main.py",
            "..\\..\\windows\\path",
        ],
    )
    def test_read_does_not_escape(self, temp_env, attack):
        # Plant a "secret" outside the brain to confirm we never read it.
        (temp_env / "secret.md").write_text("SECRET", encoding="utf-8")
        out = brain.read_voice(attack)
        assert "SECRET" not in out

    @pytest.mark.parametrize(
        "attack", ["../escape.md", "/tmp/escape.md", "../../escape.md"]
    )
    def test_write_does_not_escape(self, temp_env, attack):
        brain.write_file("voice", attack, "payload")
        # The file MUST land inside voices/, never outside.
        outside = temp_env.parent / "escape.md"
        assert not outside.exists()
        assert not (temp_env / "escape.md").exists()
