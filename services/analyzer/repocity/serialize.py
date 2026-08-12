"""CityMap serialization.

Key order and separators are fixed so that byte-comparing two runs is a meaningful
determinism check.
"""

from __future__ import annotations

import json
from typing import Any

from .schema import CityMap


def to_dict(city: CityMap) -> dict[str, Any]:
    return city.model_dump(by_alias=True, mode="json")


def to_json(city: CityMap, *, indent: int = 2) -> str:
    return json.dumps(to_dict(city), indent=indent, ensure_ascii=False, sort_keys=False) + "\n"


def strip_volatile(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop wall-clock fields so two analyses of the same tree compare equal."""
    out = {k: v for k, v in payload.items() if k != "generatedAt"}
    out["stats"] = {k: v for k, v in payload["stats"].items() if k != "durationMs"}
    return out
