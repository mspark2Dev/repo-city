"""Difference between two CityMaps.

Only works because ids are repo-relative paths rather than positions: the same file keeps
its id across analyses, so a rebuilt city can be expressed as a handful of operations
instead of a wholesale replacement. That is what lets the canvas animate the buildings
that actually changed and leave the rest alone.
"""

from __future__ import annotations

from typing import Any

from .schema import Building, CityMap, District

MOVE_EPSILON = 0.001
"""Coordinates are rounded to three places; anything smaller is noise, not a move."""


def _building_changed(before: Building, after: Building) -> bool:
    return (
        before.height != after.height
        or before.grade != after.grade
        or before.metrics != after.metrics
        or abs(before.position.x - after.position.x) > MOVE_EPSILON
        or abs(before.position.z - after.position.z) > MOVE_EPSILON
        or abs(before.footprint.w - after.footprint.w) > MOVE_EPSILON
    )


def _district_changed(before: District, after: District) -> bool:
    return (
        before.rect != after.rect
        or before.y != after.y
        or before.file_count != after.file_count
        or before.loc != after.loc
    )


def diff_cities(before: CityMap, after: CityMap) -> dict[str, Any]:
    old_buildings = {b.id: b for b in before.buildings}
    new_buildings = {b.id: b for b in after.buildings}
    old_districts = {d.id: d for d in before.districts}
    new_districts = {d.id: d for d in after.districts}

    ops: list[dict[str, Any]] = []

    for building_id in sorted(old_buildings.keys() - new_buildings.keys()):
        ops.append({"op": "remove", "id": building_id})

    for building_id in sorted(new_buildings.keys() - old_buildings.keys()):
        ops.append({"op": "add", "building": new_buildings[building_id].model_dump(by_alias=True)})

    for building_id in sorted(old_buildings.keys() & new_buildings.keys()):
        old, new = old_buildings[building_id], new_buildings[building_id]
        if _building_changed(old, new):
            ops.append(
                {
                    "op": "update",
                    "building": new.model_dump(by_alias=True),
                    "previous": {
                        "height": old.height,
                        "grade": old.grade,
                        "maxCC": old.metrics.max_cc,
                        "loc": old.metrics.loc,
                    },
                }
            )

    for district_id in sorted(new_districts.keys() - old_districts.keys()):
        ops.append(
            {"op": "district.add", "district": new_districts[district_id].model_dump(by_alias=True)}
        )
    for district_id in sorted(old_districts.keys() - new_districts.keys()):
        ops.append({"op": "district.remove", "id": district_id})
    for district_id in sorted(old_districts.keys() & new_districts.keys()):
        if _district_changed(old_districts[district_id], new_districts[district_id]):
            ops.append(
                {
                    "op": "district.update",
                    "district": new_districts[district_id].model_dump(by_alias=True),
                }
            )

    return {
        "ops": ops,
        "links": [link.model_dump(by_alias=True) for link in after.links],
        "stats": after.stats.model_dump(by_alias=True),
    }


def summarize(delta: dict[str, Any]) -> dict[str, int]:
    counts = {"added": 0, "removed": 0, "updated": 0}
    for op in delta["ops"]:
        if op["op"] == "add":
            counts["added"] += 1
        elif op["op"] == "remove":
            counts["removed"] += 1
        elif op["op"] == "update":
            counts["updated"] += 1
    return counts
