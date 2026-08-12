"""Every advertised language must actually produce metrics.

A language that silently measures nothing shows up as a city of uniformly clean buildings,
which is worse than refusing to analyze it. Each snippet contains several branches on
purpose, so silence fails the suite instead of flattering the codebase.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repocity.metrics import complexity_of
from repocity.parse import parse_source
from repocity.schema import Lang

SUFFIX: dict[str, str] = {
    "python": ".py",
    "java": ".java",
    "go": ".go",
    "rust": ".rs",
    "c": ".c",
    "cpp": ".cpp",
    "csharp": ".cs",
    "ruby": ".rb",
    "php": ".php",
    "kotlin": ".kt",
    "swift": ".swift",
    "scala": ".scala",
    "typescript": ".ts",
    "javascript": ".js",
    "lua": ".lua",
    "perl": ".pl",
    "objectivec": ".m",
    "plsql": ".sql",
}

SNIPPETS: dict[Lang, bytes] = {
    "python": b"def f(a):\n"
    b"    if a > 0 and a < 9:\n        return 1\n"
    b"    for i in range(a):\n        pass\n"
    b"    while a:\n        break\n"
    b"    return 0\n",
    "java": b"class C {\n  int f(int a) {\n"
    b"    if (a > 0 && a < 9) return 1;\n"
    b"    for (int i = 0; i < a; i++) {}\n"
    b"    while (a > 0) {}\n"
    b"    try {} catch (Exception e) {}\n    return 0;\n  }\n}\n",
    "go": b"package m\nfunc f(a int) int {\n"
    b"\tif a > 0 && a < 9 {\n\t\treturn 1\n\t}\n"
    b"\tfor i := 0; i < a; i++ {\n\t}\n"
    b"\tswitch a {\n\tcase 1:\n\t}\n\treturn 0\n}\n",
    "rust": b"fn f(a: i32) -> i32 {\n"
    b"    if a > 0 && a < 9 { return 1 }\n"
    b"    for _i in 0..a {}\n    while a > 0 {}\n"
    b"    match a { 1 => {}, _ => {} }\n    0\n}\n",
    "c": b"int f(int a) {\n"
    b"  if (a > 0 && a < 9) return 1;\n"
    b"  for (int i = 0; i < a; i++) {}\n"
    b"  while (a > 0) {}\n"
    b"  switch (a) { case 1: break; }\n  return a > 0 ? 1 : 0;\n}\n",
    "cpp": b"int f(int a) {\n"
    b"  if (a > 0 && a < 9) return 1;\n"
    b"  for (int i = 0; i < a; i++) {}\n"
    b"  try {} catch (...) {}\n"
    b"  switch (a) { case 1: break; }\n  return a ? 1 : 0;\n}\n",
    "csharp": b"class C {\n  int F(int a) {\n"
    b"    if (a > 0 && a < 9) return 1;\n"
    b"    foreach (var x in new int[0]) {}\n"
    b"    while (a > 0) {}\n"
    b"    try {} catch (System.Exception) {}\n    return a > 0 ? 1 : 0;\n  }\n}\n",
    "ruby": b"class C\n  def f(a)\n"
    b"    if a > 0 && a < 9 then 1 elsif a == 0 then 2 end\n"
    b"    while a > 0 do end\n"
    b"    case a when 1 then end\n"
    b"    begin; rescue; end\n  end\nend\n",
    "php": b"<?php\nclass C {\n  function f($a) {\n"
    b"    if ($a > 0 && $a < 9) return 1;\n"
    b"    foreach ([] as $x) {}\n    while ($a > 0) {}\n"
    b"    try {} catch (Exception $e) {}\n    return $a ? 1 : 0;\n  }\n}\n",
    "kotlin": b"class C {\n  fun f(a: Int): Int {\n"
    b"    if (a > 0 && a < 9) return 1\n"
    b"    for (i in 0..a) {}\n    while (a > 0) {}\n"
    b"    when (a) { 1 -> {} }\n"
    b"    try {} catch (e: Exception) {}\n    return 0\n  }\n}\n",
    "swift": b"class C {\n  func f(_ a: Int) -> Int {\n"
    b"    if a > 0 && a < 9 { return 1 }\n"
    b"    for _ in 0..<a {}\n    while a > 0 {}\n"
    b"    switch a { case 1: break; default: break }\n"
    b"    guard a > 0 else { return 0 }\n    return a > 0 ? 1 : 0\n  }\n}\n",
    "scala": b"class C {\n  def f(a: Int): Int = {\n"
    b"    if (a > 0 && a < 9) 1 else 2\n"
    b"    for (i <- 0 to a) {}\n    while (a > 0) {}\n"
    b"    a match { case 1 => () ; case _ => () }\n    0\n  }\n}\n",
    "typescript": b"function f(a: number): number {\n"
    b"  if (a > 0 && a < 9) return 1\n"
    b"  for (let i = 0; i < a; i++) {}\n"
    b"  while (a > 0) {}\n"
    b"  switch (a) { case 1: break }\n  return a ? 1 : 0\n}\n",
    "javascript": b"function f(a) {\n"
    b"  if (a > 0 && a < 9) return 1\n"
    b"  for (let i = 0; i < a; i++) {}\n"
    b"  try {} catch (e) {}\n  return a ? 1 : 0\n}\n",
    "lua": b"function f(a)\n"
    b"  if a > 0 and a < 9 then return 1 elseif a == 0 then return 2 end\n"
    b"  for i = 1, a do end\n  while a > 0 do break end\n  return 0\n end\n",
    "perl": b"sub f {\n  my ($a) = @_;\n"
    b"  if ($a > 0 && $a < 9) { return 1 } elsif ($a == 0) { return 2 }\n"
    b"  for my $i (1..$a) {}\n  while ($a > 0) { last }\n  return 0;\n}\n",
    "objectivec": b"@implementation C\n- (int)f:(int)a {\n"
    b"  if (a > 0 && a < 9) return 1;\n"
    b"  for (int i = 0; i < a; i++) {}\n  while (a > 0) break;\n"
    b"  switch (a) { case 1: break; }\n  return a > 0 ? 1 : 0;\n}\n@end\n",
    "plsql": b"CREATE OR REPLACE FUNCTION f(a NUMBER) RETURN NUMBER IS\nBEGIN\n"
    b"  IF a > 0 AND a < 9 THEN RETURN 1; ELSIF a = 0 THEN RETURN 2; END IF;\n"
    b"  FOR i IN 1..a LOOP NULL; END LOOP;\n"
    b"  WHILE a > 0 LOOP EXIT; END LOOP;\n  RETURN 0;\nEND;\n",
}

MIN_BRANCHES = 4


@pytest.mark.parametrize("lang", sorted(SNIPPETS))
def test_branches_are_counted(lang: str):
    """A score of 1 across the board means this language is being measured by nothing."""
    result = complexity_of(Path(f"sample{SUFFIX[lang]}"), SNIPPETS[lang].decode())
    assert result.max_cc >= MIN_BRANCHES, f"{lang} counted only {result.max_cc}"


@pytest.mark.parametrize("lang", sorted(SNIPPETS))
def test_functions_are_named_and_located(lang: str):
    """Per-function detail is what lets the interface point at the method, not the file."""
    result = complexity_of(Path(f"sample{SUFFIX[lang]}"), SNIPPETS[lang].decode())
    assert result.functions, f"{lang} reported no functions"
    assert all(fn.name for fn in result.functions)
    assert all(fn.line >= 1 for fn in result.functions)


TREE_SITTER = ("python", "java", "kotlin", "c", "cpp", "typescript", "javascript")


@pytest.mark.parametrize("lang", TREE_SITTER)
def test_languages_with_a_grammar_still_parse_for_symbols(lang: Lang):
    """These carry an import graph, which needs tree-sitter as well as lizard."""
    parsed = parse_source(SNIPPETS[lang], lang)
    assert parsed.ok and parsed.symbols >= 1


def test_every_advertised_extension_is_measurable():
    """The scanner must not promise a language lizard cannot read."""
    from repocity.metrics import supported_extensions
    from repocity.scan import LANG_BY_SUFFIX

    aliases = {".pyi": ".py", ".mts": ".ts", ".cts": ".ts", ".hh": ".hpp", ".sc": ".scala"}
    measurable = supported_extensions()
    for suffix in LANG_BY_SUFFIX:
        assert aliases.get(suffix, suffix) in measurable, f"{suffix} is advertised but unread"
