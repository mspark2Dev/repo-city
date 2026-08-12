"""Checks the model's output before a human ever sees it.

The syntax gate is the important one: broken code is a common failure mode and we already
own a parser, so catching it costs nothing. Anything that fails to parse is never shown as
a diff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..metrics import complexity_of
from ..parse import _GRAMMAR, is_parsable, parse_source
from ..schema import Lang

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9+#-]*\n(.*?)\n```\s*$", re.DOTALL)

_SUFFIX: dict[str, str] = {
    "python": ".py",
    "typescript": ".ts",
    "javascript": ".js",
    "java": ".java",
    "kotlin": ".kt",
    "c": ".c",
    "cpp": ".cpp",
}


@dataclass(slots=True)
class Verdict:
    parses: bool
    lost_symbols: list[str] = field(default_factory=list)
    before_max_cc: int = 0
    after_max_cc: int = 0
    before_loc: int = 0
    after_loc: int = 0

    @property
    def improved(self) -> bool:
        return self.after_max_cc < self.before_max_cc

    def as_dict(self) -> dict:
        return {
            "parses": self.parses,
            "lostSymbols": self.lost_symbols,
            "beforeMaxCC": self.before_max_cc,
            "afterMaxCC": self.after_max_cc,
            "beforeLoc": self.before_loc,
            "afterLoc": self.after_loc,
            "improved": self.improved,
        }


def strip_fence(text: str) -> str:
    """Models wrap whole-file output in a code fence however firmly you ask them not to."""
    match = _FENCE.match(text.strip())
    return match.group(1) if match else text.strip()


def _symbol_names(source: bytes, lang: Lang) -> set[str]:
    grammar = _GRAMMAR.get(lang)
    if grammar is None:
        return set()

    from tree_sitter_language_pack import get_parser

    root = get_parser(grammar).parse(source).root_node
    names: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in (
            "function_definition",
            "class_definition",
            "function_declaration",
            "class_declaration",
        ):
            name = node.child_by_field_name("name")
            if name is not None:
                text = source[name.start_byte : name.end_byte].decode("utf-8", "replace")
                if not text.startswith("_"):
                    names.add(text)
        stack.extend(node.children)
    return names


def verify(original: str, proposed: str, lang: Lang, path: Path | None = None) -> Verdict:
    before = original.encode()
    after = proposed.encode()

    if not is_parsable(after, lang):
        return Verdict(parses=False)

    # lizard reads the filename to pick a parser, so a real path measures more accurately
    # than the placeholder; the placeholder keeps the signature usable without one.
    named = path or Path(f"proposal{_SUFFIX.get(lang, '.txt')}")
    before_cc = complexity_of(named, original).max_cc
    after_cc = complexity_of(named, proposed).max_cc

    # A public name disappearing is not necessarily wrong, but the reviewer should know.
    lost = sorted(_symbol_names(before, lang) - _symbol_names(after, lang))

    return Verdict(
        parses=True,
        lost_symbols=lost,
        before_max_cc=before_cc,
        after_max_cc=after_cc,
        before_loc=original.count("\n") + 1,
        after_loc=proposed.count("\n") + 1,
    )


def parses(source: str, lang: Lang) -> bool:
    return is_parsable(source.encode(), lang)


def symbol_count(source: str, lang: Lang) -> int:
    return parse_source(source.encode(), lang).symbols
