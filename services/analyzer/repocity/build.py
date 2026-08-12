"""Assembles scan + parse + metrics + layout into a CityMap.

Output is deterministic: every collection is sorted by a stable key and no value depends on
iteration order, so analyzing the same tree twice produces identical bytes apart from the
wall-clock fields listed in schema.VOLATILE_FIELDS.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .cache import FileCache
from .imports import resolve_imports
from .imports.tsconfig import load_aliases
from .layout import DISTRICT_PADDING, SLACK, LayoutItem, depth_y, inset, split_rect, squarify
from .metrics import count_loc
from .parse import ImportSpec, parse_source
from .scan import ScannedFile, scan
from .schema import (
    SCHEMA_VERSION,
    Building,
    CityMap,
    District,
    Footprint,
    Grade,
    Link,
    Metrics,
    Point,
    Rect,
    Stats,
    Unresolved,
)

PROGRESS_EVERY = 50
"""Report progress in batches; a callback per file costs more than the parse."""

MAX_HEIGHT = 12.0
MIN_HEIGHT = 0.5

REFERENCE_LOC = 400.0
"""Floor for the height normalizer.

Normalizing purely against the project's own p95 makes every file in a small, uniform
project reach maximum height — the skyline stops carrying information. Blending in an
absolute reference also makes heights comparable between repositories."""
MIN_FOOTPRINT = 1.2
MAX_FOOTPRINT = 6.0

CELL_SIDE = 2.8
"""Every file gets the same cell, regardless of its metrics.

Layout is a pure function of the directory tree — which paths exist and where — and never
of the numbers attached to them. Sizing cells by symbol count meant adding one function to
one file changed that file's area, which changed its district's area, which redistributed
every rectangle in the city: a one-line edit moved all 29 buildings in the fixture.

Phase 4's transition animation, and the whole idea of comparing a city before and after a
refactoring, rest on buildings staying where they were. The cost is that footprint stops
growing past the cell, so symbol count is only legible up to that cap; height and colour
carry the signals that matter most.
"""

BAND_CLEARANCE = 1.15
"""How much thicker than its widest building a district's file band must be."""

BUILDING_GAP = 0.15
"""Clearance between a building and its treemap cell, so neighbours never touch."""

MIN_VISIBLE_FOOTPRINT = 0.2

GRADE_THRESHOLDS: tuple[tuple[int, Grade], ...] = (
    (5, "clean"),
    (10, "watch"),
    (20, "hot"),
)


def grade_for(max_cc: int) -> Grade:
    for ceiling, grade in GRADE_THRESHOLDS:
        if max_cc <= ceiling:
            return grade
    return "critical"


def height_for(loc: int, p95_loc: float) -> float:
    if loc <= 0:
        return MIN_HEIGHT
    reference = max(p95_loc, REFERENCE_LOC)
    span = MAX_HEIGHT - MIN_HEIGHT
    return round(min(MIN_HEIGHT + span * math.log1p(loc) / math.log1p(reference), MAX_HEIGHT), 3)


def footprint_for(symbols: int) -> float:
    side = 1.2 + 0.25 * math.sqrt(max(symbols, 0))
    return round(min(max(side, MIN_FOOTPRINT), MAX_FOOTPRINT), 3)


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    index = min(int(q * (len(ordered) - 1)), len(ordered) - 1)
    return float(ordered[index])


class _FileFacts:
    __slots__ = ("file", "loc", "sloc", "comments", "functions", "classes", "cc", "imports")

    def __init__(self, file: ScannedFile) -> None:
        self.file = file
        self.loc = 0
        self.sloc = 0
        self.comments = 0
        self.functions = 0
        self.classes = 0
        self.cc = (0, 0.0)
        self.imports: list[ImportSpec] = []

    @property
    def symbols(self) -> int:
        return self.functions + self.classes

    def to_cache(self) -> dict:
        return {
            "loc": self.loc,
            "sloc": self.sloc,
            "comments": self.comments,
            "functions": self.functions,
            "classes": self.classes,
            "maxCC": self.cc[0],
            "avgCC": self.cc[1],
            "imports": [[i.module, i.level] for i in self.imports],
        }

    def load_cache(self, data: dict) -> None:
        self.loc = data["loc"]
        self.sloc = data["sloc"]
        self.comments = data["comments"]
        self.functions = data["functions"]
        self.classes = data["classes"]
        self.cc = (data["maxCC"], data["avgCC"])
        self.imports = [ImportSpec(module, level) for module, level in data["imports"]]


def _analyze_file(file: ScannedFile) -> _FileFacts:
    facts = _FileFacts(file)
    raw = file.abs_path.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    counts = count_loc(text, file.lang)
    facts.loc, facts.sloc, facts.comments = counts.loc, counts.sloc, counts.comments

    parsed = parse_source(raw, file.lang)
    # Docstrings are documentation, so they move from the code tally to the comment tally.
    facts.comments += parsed.doc_lines
    facts.sloc = max(facts.sloc - parsed.doc_lines, 0)
    facts.functions = parsed.functions
    facts.classes = parsed.classes
    facts.cc = (parsed.cc.max_cc, parsed.cc.avg_cc)
    facts.imports = parsed.imports
    return facts


def _directories(paths: list[str]) -> list[str]:
    """Every directory containing a file, plus their ancestors, including the root ("")."""
    dirs = {""}
    for path in paths:
        parent = PurePosixPath(path).parent
        parts = [] if parent.as_posix() == "." else parent.as_posix().split("/")
        for i in range(len(parts)):
            dirs.add("/".join(parts[: i + 1]))
    return sorted(dirs)


ProgressHook = Callable[[int, int], None]


def build_city(
    root: Path,
    extra_excludes: tuple[str, ...] = (),
    *,
    use_cache: bool = True,
    on_progress: ProgressHook | None = None,
) -> CityMap:
    started = time.perf_counter()
    root = root.resolve()

    files = scan(root, extra_excludes)
    cache = FileCache.load(root) if use_cache else None

    facts: dict[str, _FileFacts] = {}
    total = len(files)
    for index, file in enumerate(files, start=1):
        cached = cache.get(file.rel_path, file.mtime_ns, file.size) if cache else None
        if cached is not None:
            item = _FileFacts(file)
            item.load_cache(cached)
        else:
            item = _analyze_file(file)
            if cache:
                cache.put(file.rel_path, file.mtime_ns, file.size, item.to_cache())
        facts[file.rel_path] = item
        if on_progress is not None and (index % PROGRESS_EVERY == 0 or index == total):
            on_progress(index, total)

    if cache:
        cache.prune(set(facts))
        cache.save()

    has_ts = any(f.lang in ("typescript", "javascript") for f in files)
    aliases = load_aliases(root) if has_ts else None
    resolved = resolve_imports(files, {p: f.imports for p, f in facts.items()}, aliases)
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    for (source, target), weight in resolved.edges.items():
        fan_out[source] += weight
        fan_in[target] += weight

    p95 = percentile([f.loc for f in facts.values()], 0.95)

    dirs = _directories(list(facts))
    children_of: dict[str, list[str]] = defaultdict(list)
    for path in dirs:
        if path:
            parent = PurePosixPath(path).parent.as_posix()
            children_of["" if parent == "." else parent].append(path)
    files_of: dict[str, list[str]] = defaultdict(list)
    for path in facts:
        parent = PurePosixPath(path).parent.as_posix()
        files_of["" if parent == "." else parent].append(path)

    tree = _build_tree("", children_of, files_of, facts)
    side = math.sqrt(tree.area)
    squarify([tree], Rect(x=-side / 2, z=-side / 2, w=side, d=side))

    districts: list[District] = []
    buildings: list[Building] = []
    _emit(tree, "", 0, children_of, files_of, facts, fan_in, fan_out, p95, districts, buildings)

    links = _links(resolved.edges)
    unresolved = [
        Unresolved(**{"from": f"f:{src}", "spec": spec, "reason": reason})
        for src, spec, reason in sorted(resolved.unresolved)
    ]

    return CityMap(
        schema_version=SCHEMA_VERSION,
        project_id=hashlib.sha1(str(root).encode()).hexdigest()[:12],
        root=str(root),
        generated_at=datetime.now(UTC),
        stats=Stats(
            files=len(buildings),
            loc=sum(f.loc for f in facts.values()),
            links=len(links),
            unresolved=len(unresolved),
            duration_ms=int((time.perf_counter() - started) * 1000),
        ),
        districts=districts,
        buildings=buildings,
        unresolved=unresolved,
        links=links,
    )


def _build_tree(
    path: str,
    children_of: dict[str, list[str]],
    files_of: dict[str, list[str]],
    facts: dict[str, _FileFacts],
) -> LayoutItem:
    """Area flows bottom-up; slack is added per district so growth stays local."""
    items: list[LayoutItem] = []

    for child in sorted(children_of.get(path, [])):
        items.append(_build_tree(child, children_of, files_of, facts))
    for file_path in sorted(files_of.get(path, [])):
        items.append(LayoutItem(key=file_path, area=CELL_SIDE * CELL_SIDE, is_leaf=True))

    items.sort(key=lambda i: i.key)

    file_items = [i for i in items if i.is_leaf]
    dir_items = [i for i in items if not i.is_leaf]

    files_area = sum(i.area for i in file_items) * SLACK
    dirs_area = sum(i.area for i in dir_items)
    inner_side = math.sqrt(files_area + dirs_area) or 1.0

    if file_items and dir_items:
        # A district's files get their own band. Sizing that band purely by area share
        # turns it into a thin strip whenever the subdirectories dominate — the files then
        # get slivers regardless of how much area they nominally own. Guaranteeing the
        # band is thick enough for its widest building costs the subdirectories a little
        # room, which their own slack absorbs.
        widest = max(math.sqrt(i.area) for i in file_items)
        if files_area / inner_side < widest * BAND_CLEARANCE:
            files_area = widest * BAND_CLEARANCE * inner_side
            inner_side = math.sqrt(files_area + dirs_area)
        share = files_area / (files_area + dirs_area)
    else:
        share = 1.0 if file_items else 0.0

    side = inner_side + 2 * DISTRICT_PADDING
    return LayoutItem(key=path, area=side * side, children=items, files_share=share)


def _emit(
    node: LayoutItem,
    path: str,
    depth: int,
    children_of: dict[str, list[str]],
    files_of: dict[str, list[str]],
    facts: dict[str, _FileFacts],
    fan_in: dict[str, int],
    fan_out: dict[str, int],
    p95: float,
    districts: list[District],
    buildings: list[Building],
) -> None:
    assert node.rect is not None
    inner = inset(node.rect, DISTRICT_PADDING)

    districts.append(
        District(
            id=_district_id(path),
            parent_id=_parent_id(path),
            path=path,
            depth=depth,
            rect=_round_rect(node.rect),
            y=depth_y(depth),
            file_count=len(files_of.get(path, [])),
            loc=sum(facts[p].loc for p in files_of.get(path, [])),
        )
    )

    files = [c for c in node.children if c.is_leaf]
    subdirs = [c for c in node.children if not c.is_leaf]
    if files and subdirs:
        files_rect, subdirs_rect = split_rect(inner, node.files_share)
        squarify(files, files_rect)
        squarify(subdirs, subdirs_rect)
    else:
        squarify(node.children, inner)

    for child in node.children:
        assert child.rect is not None
        if child.is_leaf:
            buildings.append(_building(child, path, facts[child.key], fan_in, fan_out, p95))
        else:
            _emit(
                child,
                child.key,
                depth + 1,
                children_of,
                files_of,
                facts,
                fan_in,
                fan_out,
                p95,
                districts,
                buildings,
            )


def _building(
    item: LayoutItem,
    district_path: str,
    facts: _FileFacts,
    fan_in: dict[str, int],
    fan_out: dict[str, int],
    p95: float,
) -> Building:
    assert item.rect is not None
    path = item.key
    max_cc, avg_cc = facts.cc
    side = max(
        min(footprint_for(facts.symbols), item.rect.w - BUILDING_GAP, item.rect.d - BUILDING_GAP),
        MIN_VISIBLE_FOOTPRINT,
    )

    return Building(
        id=f"f:{path}",
        district_id=_district_id(district_path),
        path=path,
        name=PurePosixPath(path).name,
        lang=facts.file.lang,
        position=Point(
            x=round(item.rect.x + item.rect.w / 2, 3),
            z=round(item.rect.z + item.rect.d / 2, 3),
        ),
        footprint=Footprint(w=round(side, 3), d=round(side, 3)),
        height=height_for(facts.loc, p95),
        metrics=Metrics(
            loc=facts.loc,
            sloc=facts.sloc,
            comments=facts.comments,
            symbols=facts.symbols,
            functions=facts.functions,
            classes=facts.classes,
            max_cc=max_cc,
            avg_cc=avg_cc,
            cc_density=round(max_cc / facts.loc, 4) if facts.loc else 0.0,
            fan_in=fan_in.get(path, 0),
            fan_out=fan_out.get(path, 0),
        ),
        grade=grade_for(max_cc),
    )


def _links(edges: dict[tuple[str, str], int]) -> list[Link]:
    out: list[Link] = []
    for (source, target), weight in sorted(edges.items()):
        out.append(
            Link(
                id=f"l:{source}>{target}",
                source=f"f:{source}",
                target=f"f:{target}",
                kind="import",
                weight=weight,
                bidirectional=(target, source) in edges,
            )
        )
    return out


def _district_id(path: str) -> str:
    return f"d:{path}" if path else "d:"


def _parent_id(path: str) -> str | None:
    if not path:
        return None
    parent = PurePosixPath(path).parent.as_posix()
    return _district_id("" if parent == "." else parent)


def _round_rect(rect: Rect) -> Rect:
    return Rect(x=round(rect.x, 3), z=round(rect.z, 3), w=round(rect.w, 3), d=round(rect.d, 3))
