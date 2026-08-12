"""tsconfig path alias resolution.

TypeScript projects route most of their imports through aliases (`@/components/x`), so a
resolver that only understands relative paths reports the majority of a TS codebase as
external and the dependency graph comes out nearly empty.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

_LINE_COMMENT = re.compile(r"(?<!:)//[^\n\"']*$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")


@dataclass(slots=True)
class AliasTable:
    """Alias prefix -> candidate path prefixes, both repo-relative."""

    entries: list[tuple[str, list[str]]] = field(default_factory=list)

    def expand(self, spec: str) -> list[str]:
        out: list[str] = []
        for pattern, targets in self.entries:
            if pattern.endswith("*"):
                head = pattern[:-1]
                if spec.startswith(head):
                    tail = spec[len(head) :]
                    out += [t[:-1] + tail if t.endswith("*") else t for t in targets]
            elif spec == pattern:
                out += targets
        return out


def parse_jsonc(text: str) -> dict:
    """tsconfig.json is JSON with comments and trailing commas, which json.loads rejects."""
    stripped = _BLOCK_COMMENT.sub("", _LINE_COMMENT.sub("", text))
    return json.loads(_TRAILING_COMMA.sub(r"\1", stripped))


def load_aliases(root: Path) -> AliasTable:
    table = AliasTable()

    for name in CONFIG_NAMES:
        for config in sorted(root.rglob(name)):
            if any(part in ("node_modules", ".venv", "dist") for part in config.parts):
                continue
            try:
                data = parse_jsonc(config.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue

            options = data.get("compilerOptions") or {}
            config_dir = config.parent.relative_to(root).as_posix()
            config_dir = "" if config_dir == "." else config_dir
            base_url = options.get("baseUrl", ".")
            base = _join(config_dir, base_url)

            for pattern, targets in (options.get("paths") or {}).items():
                if not isinstance(targets, list):
                    continue
                table.entries.append((pattern, [_join(base, t) for t in targets]))

            if options.get("baseUrl") is not None:
                # baseUrl alone makes every bare specifier resolvable from that directory.
                table.entries.append(("*", [_join(base, "*")]))

    table.entries.sort(key=lambda e: (-len(e[0]), e[0]))
    return table


def _join(*parts: str) -> str:
    path = PurePosixPath()
    for part in parts:
        if part in ("", "."):
            continue
        path = path / part
    return _normalize(path.as_posix())


def _normalize(path: str) -> str:
    stack: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)
