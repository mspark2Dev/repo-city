"""Prompt assembly.

The ordering here is a performance contract, not a style choice. The server caches prompt
prefixes, so everything that stays the same across commands on one file has to come first
and the user's instruction has to come last. Measured on the reference deployment: 4.51s
to first token cold, 0.58s once the prefix is cached. Putting the instruction anywhere but
last throws that away on every command.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..schema import Building, CityMap
from ..settings import llm_settings

CHARS_PER_TOKEN = 3.6
"""Rough tokens-per-character for source code; only used to stay inside the budget."""

SYSTEM_PROMPT = """You are a refactoring assistant working inside a single file of a real codebase.

Rules:
- Return the COMPLETE rewritten file. Never abbreviate, never write "unchanged" or "...".
- Preserve the file's public API unless the instruction explicitly says to change it.
- Keep the existing style: same import conventions, naming, and comment density.
- Do not add commentary outside the code."""


@dataclass(frozen=True, slots=True)
class PromptContext:
    messages: list[dict[str, str]]
    prefix: list[dict[str, str]]
    source: str
    target: Building
    included: list[str]
    dropped: list[str]

    @property
    def approx_tokens(self) -> int:
        chars = sum(len(m["content"]) for m in self.messages)
        return int(chars / CHARS_PER_TOKEN)


def _fence(lang: str) -> str:
    return {"python": "python", "typescript": "tsx", "javascript": "javascript"}.get(lang, "")


def _read(root: Path, rel_path: str) -> str | None:
    try:
        return (root / rel_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _dependencies(city: CityMap, building: Building) -> list[Building]:
    by_id = {b.id: b for b in city.buildings}
    ids = [link.target for link in city.links if link.source == building.id]
    return [by_id[i] for i in sorted(set(ids)) if i in by_id]


def build_context(city: CityMap, building: Building, instruction: str) -> PromptContext:
    root = Path(city.root)
    source = _read(root, building.path)
    if source is None:
        raise FileNotFoundError(building.path)

    budget_chars = int(llm_settings().context_budget * CHARS_PER_TOKEN)
    lang = _fence(building.lang)

    parts = [
        f"TARGET FILE: {building.path}",
        f"```{lang}\n{source}\n```",
        "",
        "METRICS: "
        f"{building.metrics.loc} lines, "
        f"{building.metrics.functions} functions, "
        f"{building.metrics.classes} classes, "
        f"max cyclomatic complexity {building.metrics.max_cc}, "
        f"imported by {building.metrics.fan_in} file(s).",
    ]
    used = sum(len(p) for p in parts)
    included: list[str] = []
    dropped: list[str] = []

    deps = _dependencies(city, building)
    if deps:
        parts.append("\nDIRECT DEPENDENCIES (for reference; do not rewrite them):")
    for dep in deps:
        body = _read(root, dep.path)
        if body is None:
            dropped.append(dep.path)
            continue
        block = f"\n{dep.path}:\n```{_fence(dep.lang)}\n{body}\n```"
        if used + len(block) > budget_chars:
            dropped.append(dep.path)
            continue
        parts.append(block)
        included.append(dep.path)
        used += len(block)

    # Everything above is stable for this file; only the instruction below changes.
    prefix = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]
    messages = [*prefix, {"role": "user", "content": f"INSTRUCTION: {instruction}"}]

    return PromptContext(
        messages=messages,
        prefix=prefix,
        source=source,
        target=building,
        included=included,
        dropped=dropped,
    )


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}

PLAN_INSTRUCTION = (
    "Before rewriting, list the concrete steps you will take. Each step is one short "
    "sentence naming what changes."
)
