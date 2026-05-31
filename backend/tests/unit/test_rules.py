"""Rule store CRUD + defaults + ID generation."""
from __future__ import annotations

import json

import pytest

from app import rules as rules_store
from app.schemas import RuleCreate


def _create(**overrides) -> RuleCreate:
    base = dict(
        name="Test rule",
        description="x",
        filter_prompt="match anything",
        action_type="reply",
        voice_file=None,
        knowledge_files=[],
        reply_prompt=None,
        confidence_threshold=0.85,
        send_mode="draft",
        label=None,
        enabled=True,
        priority=100,
    )
    base.update(overrides)
    return RuleCreate(**base)


class TestDefaultRules:
    def test_first_read_seeds_default_rules(self, temp_env):
        assert not (temp_env / "rules.json").exists()
        out = rules_store.list_rules()
        assert len(out) >= 1
        assert (temp_env / "rules.json").exists()

    def test_default_rules_are_sorted_by_priority(self, temp_env):
        out = rules_store.list_rules()
        priorities = [r.priority for r in out]
        assert priorities == sorted(priorities)


class TestCreate:
    def test_create_assigns_unique_id(self, temp_env):
        a = rules_store.create_rule(_create(name="A"))
        b = rules_store.create_rule(_create(name="B"))
        assert a.id != b.id
        assert a.id.startswith("rule-") and b.id.startswith("rule-")

    def test_created_rule_is_persisted(self, temp_env):
        r = rules_store.create_rule(_create(name="Persistent"))
        # Round-trip: re-read from disk.
        on_disk = json.loads((temp_env / "rules.json").read_text())
        assert any(item["id"] == r.id for item in on_disk)

    def test_create_with_exclude_action(self, temp_env):
        r = rules_store.create_rule(_create(name="Exc", action_type="exclude"))
        assert r.action_type == "exclude"

    def test_create_with_reply_prompt(self, temp_env):
        r = rules_store.create_rule(
            _create(name="WithPrompt", reply_prompt="Always be concise.")
        )
        assert r.reply_prompt == "Always be concise."


class TestUpdate:
    def test_update_existing(self, temp_env):
        r = rules_store.create_rule(_create(name="Original"))
        upd = rules_store.update_rule(r.id, _create(name="Renamed"))
        assert upd is not None
        assert upd.name == "Renamed"
        # Round-trip to disk.
        assert rules_store.get_rule(r.id).name == "Renamed"

    def test_update_unknown_returns_none(self, temp_env):
        assert rules_store.update_rule("does-not-exist", _create()) is None


class TestDelete:
    def test_delete_existing(self, temp_env):
        r = rules_store.create_rule(_create(name="Doomed"))
        assert rules_store.delete_rule(r.id) is True
        assert rules_store.get_rule(r.id) is None

    def test_delete_unknown_returns_false(self, temp_env):
        assert rules_store.delete_rule("nope") is False


class TestPersistence:
    def test_save_then_list_returns_same(self, temp_env):
        rules_store.create_rule(_create(name="A", priority=20))
        rules_store.create_rule(_create(name="B", priority=10))
        out = rules_store.list_rules()
        names = [r.name for r in out]
        # Sorted by priority, so B (10) before A (20).
        assert names.index("B") < names.index("A")

    def test_disabled_rule_round_trips(self, temp_env):
        r = rules_store.create_rule(_create(name="Off", enabled=False))
        assert rules_store.get_rule(r.id).enabled is False
