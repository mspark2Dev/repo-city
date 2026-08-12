"""Invariants the whole city rests on. Phase 4's animation breaks if any of these slip."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from repocity import cache
from repocity.build import build_city, grade_for, height_for
from repocity.schema import CityMap
from repocity.serialize import strip_volatile, to_dict, to_json


def test_every_file_becomes_a_building(city: CityMap, fixture_root: Path):
    expected = {
        p.relative_to(fixture_root).as_posix()
        for p in fixture_root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert {b.path for b in city.buildings} == expected
    assert city.stats.files == len(expected)


def test_output_validates_against_schema(city: CityMap):
    assert CityMap.model_validate(to_dict(city)) == city


def test_analysis_is_deterministic(fixture_root: Path):
    first = strip_volatile(to_dict(build_city(fixture_root)))
    second = strip_volatile(to_dict(build_city(fixture_root)))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_serialized_bytes_are_stable(fixture_root: Path):
    def payload(city: CityMap) -> str:
        return json.dumps(strip_volatile(json.loads(to_json(city))), indent=2)

    assert payload(build_city(fixture_root)) == payload(build_city(fixture_root))


def test_ids_are_path_based_not_positional(city: CityMap):
    for building in city.buildings:
        assert building.id == f"f:{building.path}"
    for district in city.districts:
        assert district.id == f"d:{district.path}"


def test_every_building_sits_inside_its_district(city: CityMap):
    districts = {d.id: d for d in city.districts}
    for building in city.buildings:
        rect = districts[building.district_id].rect
        half = building.footprint.w / 2
        assert rect.x <= building.position.x - half + 1e-6
        assert building.position.x + half <= rect.x + rect.w + 1e-6
        assert rect.z <= building.position.z - half + 1e-6
        assert building.position.z + half <= rect.z + rect.d + 1e-6


def test_buildings_do_not_overlap(city: CityMap):
    boxes = [
        (
            b.position.x - b.footprint.w / 2,
            b.position.z - b.footprint.d / 2,
            b.position.x + b.footprint.w / 2,
            b.position.z + b.footprint.d / 2,
            b.path,
        )
        for b in city.buildings
    ]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            apart = (
                a[0] >= b[2] - 1e-6
                or b[0] >= a[2] - 1e-6
                or a[1] >= b[3] - 1e-6
                or b[1] >= a[3] - 1e-6
            )
            assert apart, f"{a[4]} overlaps {b[4]}"


def test_district_hierarchy_is_connected(city: CityMap):
    ids = {d.id for d in city.districts}
    roots = [d for d in city.districts if d.parent_id is None]
    assert len(roots) == 1 and roots[0].path == ""
    for district in city.districts:
        if district.parent_id is not None:
            assert district.parent_id in ids


def test_links_reference_known_buildings(city: CityMap):
    ids = {b.id for b in city.buildings}
    for link in city.links:
        assert link.source in ids and link.target in ids


def test_planted_circular_dependency_is_flagged(city: CityMap):
    cycles = {(link.source, link.target) for link in city.links if link.bidirectional}
    assert ("f:orderbook/core/pricing.py", "f:orderbook/core/inventory.py") in cycles


def test_planted_complex_function_is_critical(city: CityMap):
    settlement = next(b for b in city.buildings if b.path.endswith("core/settlement.py"))
    assert settlement.metrics.max_cc > 20
    assert settlement.grade == "critical"


def test_stdlib_imports_are_external_not_missing(city: CityMap):
    reasons = {u.spec: u.reason for u in city.unresolved}
    assert reasons.get("decimal") == "external"
    assert "not_found" not in reasons.values()


def test_grade_boundaries():
    assert grade_for(0) == grade_for(5) == "clean"
    assert grade_for(6) == grade_for(10) == "watch"
    assert grade_for(11) == grade_for(20) == "hot"
    assert grade_for(21) == "critical"


def test_height_is_monotonic_and_capped():
    heights = [height_for(loc, 500) for loc in (0, 10, 100, 1000, 100_000)]
    assert heights == sorted(heights)
    assert heights[-1] <= 28.0


def test_metrics_use_the_documented_wire_names(city: CityMap):
    """DESIGN.md specifies maxCC/avgCC; the camelCase generator would produce maxCc."""
    metrics = to_dict(city)["buildings"][0]["metrics"]
    assert {"maxCC", "avgCC", "ccDensity", "fanIn", "fanOut"} <= set(metrics)


def test_cache_round_trips(fixture_root: Path, tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path))
    cold = build_city(fixture_root)
    warm = build_city(fixture_root)
    assert strip_volatile(to_dict(cold)) == strip_volatile(to_dict(warm))
    assert cache.FileCache.load(fixture_root).entries


def test_cache_invalidates_when_the_analyzer_changes(fixture_root: Path, tmp_path, monkeypatch):
    """Keying only on mtime and size would serve old metrics after a logic change."""
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path))
    build_city(fixture_root)
    assert cache.FileCache.load(fixture_root).entries

    monkeypatch.setattr(cache, "analyzer_fingerprint", lambda: "some-other-build")
    assert cache.FileCache.load(fixture_root).entries == {}


def test_cache_stays_out_of_the_analyzed_repository(fixture_root: Path, tmp_path, monkeypatch):
    """repoCity is pointed at other people's checkouts; it must not leave files in them."""
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path))
    build_city(fixture_root)
    assert not (fixture_root / ".repocity").exists()
    assert list(tmp_path.glob("*.json"))


def test_layout_does_not_depend_on_metrics(fixture_root: Path, tmp_path, monkeypatch):
    """Editing one file must not move any other building.

    Phase 4's transition animation and before/after comparison both rest on this: if a
    one-line edit reshuffles the city, "the building that changed" stops being a thing you
    can point at.
    """
    monkeypatch.setenv("REPOCITY_CACHE_DIR", str(tmp_path / "cache"))
    project = tmp_path / "project"
    shutil.copytree(fixture_root, project)

    before = {b.id: (b.position.x, b.position.z) for b in build_city(project).buildings}
    edited = project / "orderbook" / "util" / "money.py"
    edited.write_text(
        edited.read_text() + "\n\ndef added():\n    if 1:\n        return 2\n    return 3\n",
        encoding="utf-8",
    )
    after = {b.id: (b.position.x, b.position.z) for b in build_city(project).buildings}

    assert before == after
