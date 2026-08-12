"""Line counting.

Comment detection is deliberately lexical rather than AST-based: it runs on every file
including ones we have no grammar for, and an approximate comment count is enough to
separate documentation from code.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import Lang

_LINE_COMMENT: dict[str, tuple[str, ...]] = {
    "python": ("#",),
    "ruby": ("#",),
    "perl": ("#",),
    "r": ("#",),
    "gdscript": ("#",),
    "erlang": ("%",),
    "fortran": ("!",),
    "plsql": ("--",),
    "smalltalk": ('"',),
    "php": ("//", "#"),
}
_DEFAULT_COMMENT = ("//",)


@dataclass(frozen=True, slots=True)
class LocCounts:
    loc: int
    sloc: int
    comments: int


def count_loc(source: str, lang: Lang) -> LocCounts:
    prefixes = _LINE_COMMENT.get(lang, _DEFAULT_COMMENT)
    total = 0
    comments = 0
    code = 0

    for raw in source.splitlines():
        total += 1
        line = raw.strip()
        if not line:
            continue
        if line.startswith(prefixes):
            comments += 1
        else:
            code += 1

    return LocCounts(loc=total, sloc=code, comments=comments)
