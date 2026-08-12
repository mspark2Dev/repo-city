"""Cyclomatic complexity per function.

CC = 1 + branch count. Which node types count as a branch is data, not code, so adding a
language means editing cc_rules.json.

The file-level number reported to the UI is the *maximum* over functions, not the average:
one 40-branch function inside an otherwise tidy 400-line file is what you want to see, and
an average would dilute it away (DESIGN.md decision 4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tree_sitter import Node

_RULES_PATH = Path(__file__).with_name("cc_rules.json")


@dataclass(frozen=True, slots=True)
class ComplexityResult:
    max_cc: int
    avg_cc: float
    total_cc: int
    function_count: int


@dataclass(frozen=True, slots=True)
class _Rules:
    functions: frozenset[str]
    branches: frozenset[str]
    operator_branches: dict[str, frozenset[str]]


@lru_cache(maxsize=8)
def _rules_for(grammar: str) -> _Rules | None:
    data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    entry = data.get(grammar)
    if entry is None:
        return None

    branches: set[str] = set()
    operators: dict[str, set[str]] = {}
    for spec in entry["branch"]:
        # "binary_expression:&&" counts only that operator, not every binary expression.
        node_type, _, operator = spec.partition(":")
        if operator:
            operators.setdefault(node_type, set()).add(operator)
        else:
            branches.add(node_type)

    return _Rules(
        functions=frozenset(entry["function"]),
        branches=frozenset(branches),
        operator_branches={k: frozenset(v) for k, v in operators.items()},
    )


def complexity(root: Node, source: bytes, grammar: str) -> ComplexityResult:
    rules = _rules_for(grammar)
    if rules is None:
        return ComplexityResult(max_cc=0, avg_cc=0.0, total_cc=0, function_count=0)

    scores = [1 + _count_branches(fn, source, rules) for fn in _functions(root, rules)]
    if not scores:
        # Module-level code still has branches worth reporting as the file's complexity.
        module_cc = 1 + _count_branches(root, source, rules)
        return ComplexityResult(module_cc, float(module_cc), module_cc, 0)

    total = sum(scores)
    return ComplexityResult(
        max_cc=max(scores),
        avg_cc=round(total / len(scores), 2),
        total_cc=total,
        function_count=len(scores),
    )


def _functions(node: Node, rules: _Rules) -> list[Node]:
    found: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in rules.functions and current is not node:
            found.append(current)
        stack.extend(current.children)
    return found


def _count_branches(scope: Node, source: bytes, rules: _Rules) -> int:
    """Count branches inside `scope`, excluding nested functions, which score separately."""
    count = 0
    stack = list(scope.children)
    while stack:
        node = stack.pop()
        if node.type in rules.functions:
            continue
        if (
            node.type in rules.branches
            or node.type in rules.operator_branches
            and _operator_of(node, source) in (rules.operator_branches[node.type])
        ):
            count += 1
        stack.extend(node.children)
    return count


def _operator_of(node: Node, source: bytes) -> str:
    operator = node.child_by_field_name("operator")
    if operator is None:
        return ""
    return source[operator.start_byte : operator.end_byte].decode("utf-8", errors="replace")
