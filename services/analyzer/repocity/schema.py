"""Single source of truth for the CityMap format.

TypeScript types are generated from this module's JSON Schema; never hand-edit them.
Field names are camelCase on the wire and snake_case in Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SCHEMA_VERSION = "1.0"

Grade = Literal["clean", "watch", "hot", "critical"]
Lang = Literal[
    "python",
    "typescript",
    "javascript",
    "java",
    "go",
    "rust",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "kotlin",
    "swift",
    "scala",
    "other",
]


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Rect(Model):
    x: float
    z: float
    w: float
    d: float


class Point(Model):
    x: float
    z: float


class Footprint(Model):
    w: float
    d: float


class Metrics(Model):
    # CC-related aliases are spelled out: the generated camelCase would be "maxCc",
    # and the wire format is specified as "maxCC" in DESIGN.md.
    loc: int
    sloc: int
    comments: int
    symbols: int
    functions: int
    classes: int
    max_cc: int = Field(alias="maxCC")
    avg_cc: float = Field(alias="avgCC")
    cc_density: float = Field(alias="ccDensity")
    fan_in: int
    fan_out: int


class District(Model):
    id: str
    parent_id: str | None
    path: str
    depth: int
    rect: Rect
    y: float
    file_count: int
    loc: int


class Building(Model):
    id: str
    district_id: str
    path: str
    name: str
    lang: Lang
    position: Point
    footprint: Footprint
    height: float
    metrics: Metrics
    grade: Grade


class Link(Model):
    id: str
    source: str
    target: str
    kind: Literal["import"]
    weight: int
    bidirectional: bool


class Unresolved(Model):
    # `from` is a Python keyword, so the field is aliased rather than renamed on the wire.
    from_: str = Field(alias="from")
    spec: str
    reason: Literal["external", "not_found", "unsupported"]


class Stats(Model):
    files: int
    loc: int
    links: int
    unresolved: int
    duration_ms: int


class CityMap(Model):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    root: str
    generated_at: datetime
    stats: Stats
    districts: list[District]
    buildings: list[Building]
    unresolved: list[Unresolved]
    links: list[Link]


VOLATILE_FIELDS = ("generatedAt", "stats.durationMs")
"""Fields excluded from determinism checks: wall-clock values, not analysis output."""
