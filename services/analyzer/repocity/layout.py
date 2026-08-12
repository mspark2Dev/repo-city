"""Squarified treemap layout for districts and buildings.

Two properties matter more than packing density, and both come from DESIGN.md decision 6:

1. Determinism — the same repository always produces the same coordinates.
2. Stability — editing a file must not move other buildings. Placement is therefore
   ordered by name rather than by size, and every district reserves slack area, so a
   file growing by a few hundred lines does not reshuffle the city.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .schema import Rect

SLACK = 1.25
"""Extra district area reserved so growth does not force a re-layout."""

DISTRICT_PADDING = 0.6
DEPTH_STEP = 0.4


@dataclass(slots=True)
class LayoutItem:
    """A leaf (building) or subtree (district) competing for area."""

    key: str
    area: float
    rect: Rect | None = None
    children: list[LayoutItem] = field(default_factory=list)
    is_leaf: bool = False
    files_share: float = 0.0
    """Fraction of this district's inner rect reserved for its own files."""


def squarify(items: list[LayoutItem], rect: Rect) -> None:
    """Assign a sub-rectangle of `rect` to each item, in the order given.

    Items are laid out in their existing order — callers sort by name, not by area, so
    the result is stable across analyses.
    """
    if not items:
        return

    total = sum(i.area for i in items) or 1.0
    scale = (rect.w * rect.d) / total
    remaining = list(items)
    x, z, w, d = rect.x, rect.z, rect.w, rect.d

    while remaining:
        row, row_area = _next_row(remaining, min(w, d), scale)
        if min(w, d) == w:
            row_height = row_area / w if w else 0.0
            _place_row(row, x, z, w, row_height, horizontal=True, scale=scale)
            z += row_height
            d -= row_height
        else:
            row_width = row_area / d if d else 0.0
            _place_row(row, x, z, row_width, d, horizontal=False, scale=scale)
            x += row_width
            w -= row_width
        remaining = remaining[len(row) :]


def _next_row(items: list[LayoutItem], side: float, scale: float) -> tuple[list[LayoutItem], float]:
    """Take items into a row while doing so improves the worst aspect ratio."""
    row: list[LayoutItem] = []
    row_area = 0.0
    best = math.inf

    for item in items:
        area = item.area * scale
        ratio = _worst_ratio(row_area + area, side, [i.area * scale for i in row] + [area])
        if row and ratio > best:
            break
        row.append(item)
        row_area += area
        best = ratio

    return row, row_area


def _worst_ratio(row_area: float, side: float, areas: list[float]) -> float:
    if row_area <= 0 or side <= 0:
        return math.inf
    thickness = row_area / side
    return max(max(thickness / a * thickness, a / thickness / thickness) for a in areas if a > 0)


def _place_row(
    row: list[LayoutItem], x: float, z: float, w: float, d: float, *, horizontal: bool, scale: float
) -> None:
    offset = 0.0
    for item in row:
        area = item.area * scale
        if horizontal:
            width = area / d if d else 0.0
            item.rect = Rect(x=x + offset, z=z, w=width, d=d)
            offset += width
        else:
            height = area / w if w else 0.0
            item.rect = Rect(x=x, z=z + offset, w=w, d=height)
            offset += height


def split_rect(rect: Rect, first_share: float) -> tuple[Rect, Rect]:
    """Cut a rect along its longer axis, giving `first_share` of the area to the first part.

    Files and subdirectories are laid out in separate bands rather than competing in one
    treemap. Mixing them means a large subtree and a small file land in the same row, and
    the file gets a sliver — which is how a README ends up 0.13 units wide.
    """
    share = min(max(first_share, 0.0), 1.0)
    if rect.w >= rect.d:
        width = rect.w * share
        return (
            Rect(x=rect.x, z=rect.z, w=width, d=rect.d),
            Rect(x=rect.x + width, z=rect.z, w=rect.w - width, d=rect.d),
        )
    depth = rect.d * share
    return (
        Rect(x=rect.x, z=rect.z, w=rect.w, d=depth),
        Rect(x=rect.x, z=rect.z + depth, w=rect.w, d=rect.d - depth),
    )


def inset(rect: Rect, padding: float) -> Rect:
    """Shrink a rect, keeping it non-degenerate for small districts."""
    pad = min(padding, rect.w / 4, rect.d / 4)
    return Rect(x=rect.x + pad, z=rect.z + pad, w=rect.w - 2 * pad, d=rect.d - 2 * pad)


def depth_y(depth: int) -> float:
    return round(depth * DEPTH_STEP, 4)
