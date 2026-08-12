"""Agent behaviour that must hold without touching a model endpoint."""

from __future__ import annotations

import os

import pytest

from repocity.agent.context import build_context
from repocity.agent.patch import apply_change, revert, unified_diff
from repocity.agent.verify import strip_fence, verify
from repocity.schema import CityMap


@pytest.fixture
def target(city: CityMap):
    return next(b for b in city.buildings if b.path.endswith("core/settlement.py"))


def test_instruction_comes_last_and_the_prefix_is_stable(city: CityMap, target):
    """The prefill cache only helps if everything reusable precedes the instruction."""
    first = build_context(city, target, "Split the biggest function.")
    second = build_context(city, target, "Add type hints instead.")

    assert first.prefix == second.prefix
    assert first.messages[: len(first.prefix)] == first.prefix
    assert first.messages[-1]["content"].startswith("INSTRUCTION:")
    assert "Split the biggest function." in first.messages[-1]["content"]
    assert "Split the biggest function." not in "".join(m["content"] for m in first.prefix)


def test_context_includes_direct_dependencies(city: CityMap, target):
    context = build_context(city, target, "anything")
    assert "orderbook/core/models.py" in context.included
    assert "OrderLine" in context.messages[1]["content"]


def test_context_stays_within_budget(city: CityMap, target, monkeypatch):
    from repocity import settings

    monkeypatch.setattr(
        settings,
        "llm_settings",
        lambda: settings.LLMSettings("http://x", "m", "k", 1000, 100),
    )
    import repocity.agent.context as context_module

    monkeypatch.setattr(context_module, "llm_settings", settings.llm_settings)
    context = build_context(city, target, "anything")
    assert context.dropped or not context.included


@pytest.mark.parametrize(
    ("wrapped", "expected"),
    [
        ("```python\nx = 1\n```", "x = 1"),
        ("```\nx = 1\n```", "x = 1"),
        ("x = 1", "x = 1"),
    ],
)
def test_code_fences_are_stripped(wrapped: str, expected: str):
    assert strip_fence(wrapped) == expected


def test_unparsable_output_is_rejected():
    verdict = verify("def f():\n    return 1\n", "def f(:\n    return 1\n", "python")
    assert not verdict.parses


def test_complexity_improvement_is_reported():
    before = "def f(a):\n" + "".join(f"    if a == {i}: return {i}\n" for i in range(12))
    after = "TABLE = {i: i for i in range(12)}\n\n\ndef f(a):\n    return TABLE.get(a)\n"
    verdict = verify(before, after, "python")
    assert verdict.parses and verdict.improved
    assert verdict.after_max_cc < verdict.before_max_cc


def test_lost_public_symbols_are_flagged():
    verdict = verify("def keep():\n    pass\n", "def renamed():\n    pass\n", "python")
    assert verdict.lost_symbols == ["keep"]


def test_private_symbols_are_not_flagged():
    verdict = verify("def _helper():\n    pass\n", "def _other():\n    pass\n", "python")
    assert verdict.lost_symbols == []


def test_diff_is_unified_and_labelled():
    diff = unified_diff("a\n", "b\n", "src/x.py")
    assert diff.startswith("--- a/src/x.py\n+++ b/src/x.py\n")
    assert "-a\n" in diff and "+b\n" in diff


def test_apply_then_revert_restores_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path / "state"))
    project = tmp_path / "project"
    project.mkdir()
    source = project / "mod.py"
    original = "def f():\n    return 1\n"
    source.write_text(original, encoding="utf-8")

    applied = apply_change("proj", "task", project, "mod.py", "def f():\n    return 2\n")
    assert source.read_text(encoding="utf-8") == "def f():\n    return 2\n"

    assert revert(applied.snapshot_id) == ["mod.py"]
    assert source.read_text(encoding="utf-8") == original


def test_writes_outside_the_project_are_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path / "state"))
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "outside.py").write_text("secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the project"):
        apply_change("proj", "task", project, "../outside.py", "overwritten\n")
    assert (tmp_path / "outside.py").read_text(encoding="utf-8") == "secret\n"


def test_reverting_an_unknown_snapshot_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        revert("nope/nope")


@pytest.mark.skipif(
    os.environ.get("REPOCITY_LIVE_LLM") != "1",
    reason="needs a reachable model endpoint; set REPOCITY_LIVE_LLM=1",
)
def test_prefix_cache_makes_a_second_command_faster(city: CityMap, target):
    """Regression guard for the ordering contract in agent/context.py.

    Measured on the reference deployment: 4.44s cold, 0.51s warm on a ~6k token prefix.
    """
    import asyncio
    import time

    from repocity.agent.llm import LLMAdapter

    adapter = LLMAdapter()

    async def first_token(instruction: str) -> float:
        context = build_context(city, target, instruction)
        start = time.perf_counter()
        async for _ in adapter.stream(context.messages, max_tokens=1):
            return time.perf_counter() - start
        return float("inf")

    async def run() -> tuple[float, float]:
        return await first_token("Rename things."), await first_token("Add type hints.")

    cold, warm = asyncio.run(run())
    assert warm <= cold
