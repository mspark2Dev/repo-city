"""Every supported language must actually produce metrics.

A rule file that names a node type the grammar does not have fails silently: complexity
comes out as 1 everywhere and the city looks uniformly clean. Each snippet below contains
several branches on purpose, so a wrong name shows up as a failing test rather than as a
codebase that appears tidy.
"""

from __future__ import annotations

import pytest

from repocity.parse import parse_source
from repocity.schema import Lang

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
}

MIN_BRANCHES = 4


@pytest.mark.parametrize("lang", sorted(SNIPPETS))
def test_the_snippet_parses(lang: Lang):
    assert parse_source(SNIPPETS[lang], lang).ok, f"{lang} snippet does not parse"


@pytest.mark.parametrize("lang", sorted(SNIPPETS))
def test_branches_are_counted(lang: Lang):
    """Complexity of 1 means the rule file names nodes this grammar does not produce."""
    result = parse_source(SNIPPETS[lang], lang)
    assert result.cc.max_cc >= MIN_BRANCHES, f"{lang} counted only {result.cc.max_cc}"


@pytest.mark.parametrize("lang", sorted(SNIPPETS))
def test_symbols_are_counted(lang: Lang):
    assert parse_source(SNIPPETS[lang], lang).symbols >= 1, f"{lang} found no symbols"
