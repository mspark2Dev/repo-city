"""Cyclomatic complexity, measured by lizard.

This was hand-rolled on top of tree-sitter: a rules file naming the branch nodes of each
grammar, plus a test per language to catch a name the grammar does not have — because a
wrong name produces a complexity of 1 and a city that looks uniformly clean.

Measured against lizard on 400 files of a real Java codebase, the two agreed on 399 of
them. Equal quality with none of that upkeep, and lizard reads 27 languages to the
fourteen the rules file covered, so files that used to be grey now carry a colour.

tree-sitter stays for what lizard does not do: imports, symbol names, and checking that
what the agent wrote still parses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import lizard


@dataclass(frozen=True, slots=True)
class FunctionComplexity:
    name: str
    cc: int
    line: int
    lines: int


@dataclass(frozen=True, slots=True)
class ComplexityResult:
    max_cc: int
    avg_cc: float
    total_cc: int
    function_count: int
    functions: list[FunctionComplexity] = field(default_factory=list)


EMPTY = ComplexityResult(max_cc=0, avg_cc=0.0, total_cc=0, function_count=0)


def supported_extensions() -> frozenset[str]:
    """Extensions lizard can measure, as `.py` rather than `py`."""
    found: set[str] = set()
    for language in lizard.languages():
        for extension in getattr(language, "ext", ()):
            found.add(f".{extension}")
    return frozenset(found)


def complexity_of(path: Path, source: str) -> ComplexityResult:
    """Measure a file already read from disk.

    lizard picks its reader from the filename, so the path matters even though the content
    is passed in; reading it a second time would double the I/O for no gain.
    """
    try:
        analysis = lizard.analyze_file.analyze_source_code(str(path), source)
    except Exception:
        # A reader that trips on unusual input should cost that one file, not the analysis.
        return EMPTY

    functions = [
        FunctionComplexity(
            name=fn.name,
            cc=fn.cyclomatic_complexity,
            line=fn.start_line,
            lines=fn.length,
        )
        for fn in analysis.function_list
    ]
    if not functions:
        return EMPTY

    scores = [fn.cc for fn in functions]
    total = sum(scores)
    return ComplexityResult(
        max_cc=max(scores),
        avg_cc=round(total / len(scores), 2),
        total_cc=total,
        function_count=len(scores),
        functions=sorted(functions, key=lambda fn: (-fn.cc, fn.line)),
    )
