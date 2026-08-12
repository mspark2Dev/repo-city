"""Deltas are what make the transition animation possible; if they lie, the city lies."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from repocity.build import build_city
from repocity.delta import diff_cities, summarize

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "sample-project"


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "project"
    shutil.copytree(FIXTURE, root)
    return root


def test_an_unchanged_repository_produces_no_operations(project):
    before = build_city(project)
    after = build_city(project)
    assert diff_cities(before, after)["ops"] == []


def test_editing_one_file_touches_only_that_building(project):
    before = build_city(project)
    target = project / "orderbook" / "util" / "money.py"
    target.write_text(target.read_text() + "\n\ndef extra():\n    return 1\n", encoding="utf-8")

    delta = diff_cities(before, build_city(project))
    updated = [op for op in delta["ops"] if op["op"] == "update"]
    assert [op["building"]["path"] for op in updated] == ["orderbook/util/money.py"]
    assert summarize(delta) == {"added": 0, "removed": 0, "updated": 1}


def test_splitting_a_file_removes_one_building_and_adds_others(project):
    before = build_city(project)
    core = project / "orderbook" / "core"
    (core / "settlement.py").unlink()
    (core / "settle_eu.py").write_text("def eu(x):\n    return x\n", encoding="utf-8")
    (core / "settle_us.py").write_text("def us(x):\n    return x\n", encoding="utf-8")

    delta = diff_cities(before, build_city(project))
    removed = [op["id"] for op in delta["ops"] if op["op"] == "remove"]
    added = [op["building"]["path"] for op in delta["ops"] if op["op"] == "add"]
    assert removed == ["f:orderbook/core/settlement.py"]
    assert added == ["orderbook/core/settle_eu.py", "orderbook/core/settle_us.py"]


def test_an_update_carries_the_previous_values_for_the_transition(project):
    before = build_city(project)
    target = project / "orderbook" / "core" / "settlement.py"
    target.write_text(
        "def settle(order, region, currency, flags):\n    return 0\n", encoding="utf-8"
    )

    delta = diff_cities(before, build_city(project))
    update = next(
        op
        for op in delta["ops"]
        if op["op"] == "update" and op["building"]["path"].endswith("settlement.py")
    )
    assert update["previous"]["maxCC"] == 29
    assert update["previous"]["grade"] == "critical"
    assert update["building"]["grade"] == "clean"


def test_dropping_an_import_updates_the_file_that_was_imported(project):
    """fan-in is a metric too: the other end of a removed edge really has changed."""
    before = build_city(project)
    target = project / "orderbook" / "core" / "settlement.py"
    target.write_text(
        "def settle(order, region, currency, flags):\n    return 0\n", encoding="utf-8"
    )

    delta = diff_cities(before, build_city(project))
    touched = {op["building"]["path"] for op in delta["ops"] if op["op"] == "update"}
    assert touched == {"orderbook/core/settlement.py", "orderbook/core/models.py"}


def test_delta_carries_the_new_link_set(project):
    before = build_city(project)
    (project / "orderbook" / "util" / "money.py").write_text(
        "from ..core.models import Order\n\n\ndef to_cents(v):\n    return int(v * 100)\n",
        encoding="utf-8",
    )
    delta = diff_cities(before, build_city(project))
    sources = {link["source"] for link in delta["links"]}
    assert "f:orderbook/util/money.py" in sources
