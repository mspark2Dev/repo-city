"""Import resolution is where the dependency graph gets its credibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from repocity.build import build_city
from repocity.imports.tsconfig import AliasTable, load_aliases, parse_jsonc

WEB_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "sample-web"


@pytest.fixture(scope="module")
def web_city():
    return build_city(WEB_FIXTURE, use_cache=False)


def test_jsonc_tolerates_comments_and_trailing_commas():
    parsed = parse_jsonc('{\n // note\n "a": [1, 2,],\n /* block */ "b": 1,\n}')
    assert parsed == {"a": [1, 2], "b": 1}


def test_alias_expansion():
    table = AliasTable(entries=[("@/*", ["src/*"]), ("~lib", ["src/lib/index.ts"])])
    assert table.expand("@/components/x") == ["src/components/x"]
    assert table.expand("~lib") == ["src/lib/index.ts"]
    assert table.expand("react") == []


def test_aliases_load_from_tsconfig():
    patterns = {pattern for pattern, _ in load_aliases(WEB_FIXTURE).entries}
    assert {"@/*", "~lib"} <= patterns


def test_wildcard_alias_resolves(web_city):
    edges = {(link.source, link.target) for link in web_city.links}
    assert ("f:src/app.tsx", "f:src/lib/money.ts") in edges
    assert ("f:src/app.tsx", "f:src/components/OrderRow.tsx") in edges


def test_exact_alias_to_a_concrete_file_resolves(web_city):
    edges = {(link.source, link.target) for link in web_city.links}
    assert ("f:src/components/OrderRow.tsx", "f:src/lib/index.ts") in edges


def test_packages_stay_external(web_city):
    assert {u.spec for u in web_city.unresolved} == {"react"}
