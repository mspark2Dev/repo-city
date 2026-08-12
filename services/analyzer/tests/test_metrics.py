from __future__ import annotations

from repocity.metrics import count_loc
from repocity.parse import parse_source


def test_python_docstrings_count_as_documentation():
    source = (
        b'"""Module doc.\n\nSecond line.\n"""\n\n\ndef f():\n    """One line."""\n    return 1\n'
    )
    assert parse_source(source, "python").doc_lines == 5


def test_docstring_detection_survives_both_grammar_shapes():
    """The literal sits in the body's first slot; only its wrapper varies by grammar."""
    assert parse_source(b'def f():\n    """doc"""\n    return 1\n', "python").doc_lines == 1


def test_line_counts_split_code_and_comments():
    counts = count_loc("# note\n\nx = 1\ny = 2\n", "python")
    assert (counts.loc, counts.sloc, counts.comments) == (4, 2, 1)


def test_complexity_counts_boolean_operators_as_branches():
    from pathlib import Path

    from repocity.metrics import complexity_of

    plain = complexity_of(Path("a.ts"), "function f() { return 1 + 2 }\n").max_cc
    branching = complexity_of(Path("a.ts"), "function f() { return b && c }\n").max_cc
    assert branching == plain + 1
