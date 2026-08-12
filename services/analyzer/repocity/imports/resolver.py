"""Turns raw import specifiers into file-to-file edges.

Anything that cannot be resolved to a file in the repository is recorded as unresolved
rather than dropped. That count is the honesty of the whole graph, so it is reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ..parse import ImportSpec
from ..scan import ScannedFile
from .tsconfig import AliasTable

_PY_SUFFIXES = (".py", ".pyi")
_JAVA_SUFFIXES = (".java", ".kt")
_C_SUFFIXES = (".h", ".hpp", ".hh", ".c", ".cc", ".cpp", ".cxx")
_JS_SUFFIXES = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs")
_INDEX_STEMS = ("index", "__init__")

# Import roots to try for absolute Python imports, in order.
_SOURCE_ROOTS = ("", "src", "lib", "app")


@dataclass(slots=True)
class ResolvedImports:
    edges: dict[tuple[str, str], int] = field(default_factory=dict)
    unresolved: list[tuple[str, str, str]] = field(default_factory=list)

    def add_edge(self, source: str, target: str) -> None:
        if source == target:
            return
        key = (source, target)
        self.edges[key] = self.edges.get(key, 0) + 1

    def add_unresolved(self, source: str, spec: str, reason: str) -> None:
        self.unresolved.append((source, spec, reason))


def resolve_imports(
    files: list[ScannedFile],
    parsed: dict[str, list[ImportSpec]],
    aliases: AliasTable | None = None,
) -> ResolvedImports:
    index = {f.rel_path: f for f in files}
    java_index = _java_index(files)
    out = ResolvedImports()

    for rel_path in sorted(parsed):
        source_file = index.get(rel_path)
        if source_file is None:
            continue
        for spec in parsed[rel_path]:
            if source_file.lang == "python":
                target = _resolve_python(rel_path, spec, index)
            elif source_file.lang in ("java", "kotlin"):
                target = _resolve_java(spec, java_index)
            elif source_file.lang in ("c", "cpp"):
                target = _resolve_include(rel_path, spec, index)
            else:
                target = _resolve_js(rel_path, spec, index, aliases)

            label = _spec_label(spec)
            if target is not None:
                out.add_edge(rel_path, target)
            elif _looks_local(spec):
                out.add_unresolved(rel_path, label, "not_found")
            else:
                out.add_unresolved(rel_path, label, "external")

    return out


def _spec_label(spec: ImportSpec) -> str:
    return "." * spec.level + spec.module if spec.level else spec.module


def _java_index(files: list[ScannedFile]) -> dict[str, str]:
    """Maps a fully qualified class name to its file.

    Java says where a class lives — `com.foo.Bar` is `com/foo/Bar.java` somewhere under a
    source root — but not where that root starts, so the lookup is by path suffix. A name
    claimed by more than one file is dropped rather than guessed at.
    """
    index: dict[str, str] = {}
    clashes: set[str] = set()
    for file in files:
        if file.lang not in ("java", "kotlin"):
            continue
        parts = PurePosixPath(file.rel_path).with_suffix("").parts
        for start in range(len(parts)):
            name = ".".join(parts[start:])
            if name in index and index[name] != file.rel_path:
                clashes.add(name)
            index.setdefault(name, file.rel_path)
    for name in clashes:
        del index[name]
    return index


def _resolve_java(spec: ImportSpec, java_index: dict[str, str]) -> str | None:
    name = spec.module
    if name.endswith(".*"):
        return None  # A wildcard names a package, not a file.
    if name in java_index:
        return java_index[name]
    # `import static com.foo.Bar.method` ends at a member, so try the class it belongs to.
    parent, _, _ = name.rpartition(".")
    return java_index.get(parent)


def _resolve_include(rel_path: str, spec: ImportSpec, index: dict) -> str | None:
    """A quoted include is relative to the including file, then to any include root."""
    here = (PurePosixPath(rel_path).parent / spec.module).as_posix()
    normalized = _normalize(here)
    if normalized in index:
        return normalized

    # Projects also include by a path relative to an include/ or src/ root.
    tail = spec.module.lstrip("./")
    matches = [path for path in index if path == tail or path.endswith(f"/{tail}")]
    return matches[0] if len(matches) == 1 else None


def _looks_local(spec: ImportSpec) -> bool:
    return spec.level > 0 or spec.module.startswith((".", "@/", "~/", "#"))


def _candidates(base: PurePosixPath, suffixes: tuple[str, ...]) -> list[str]:
    # The bare path comes first: an alias may already name a concrete file.
    out = [base.as_posix()]
    out += [f"{base}{suffix}" for suffix in suffixes]
    out += [f"{base}/{stem}{suffix}" for stem in _INDEX_STEMS for suffix in suffixes]
    return out


def _first_existing(candidates: list[str], index: dict[str, object]) -> str | None:
    return next((c for c in candidates if c in index), None)


def _resolve_python(rel_path: str, spec: ImportSpec, index: dict) -> str | None:
    parts = spec.module.split(".") if spec.module else []

    if spec.level > 0:
        # `from . import x` is level 1 and resolves against the importer's own package.
        package = PurePosixPath(rel_path).parent
        for _ in range(spec.level - 1):
            package = package.parent
        base = package.joinpath(*parts) if parts else package
        return _first_existing(_candidates(base, _PY_SUFFIXES), index)

    for root in _SOURCE_ROOTS:
        base = PurePosixPath(root).joinpath(*parts) if root else PurePosixPath(*parts)
        hit = _first_existing(_candidates(base, _PY_SUFFIXES), index)
        if hit is not None:
            return hit
    return None


def _resolve_js(
    rel_path: str, spec: ImportSpec, index: dict, aliases: AliasTable | None
) -> str | None:
    if spec.module.startswith("."):
        base = (PurePosixPath(rel_path).parent / spec.module).as_posix()
        return _first_existing(_candidates(PurePosixPath(_normalize(base)), _JS_SUFFIXES), index)

    if aliases is None:
        return None
    for candidate in aliases.expand(spec.module):
        hit = _first_existing(_candidates(PurePosixPath(candidate), _JS_SUFFIXES), index)
        if hit is not None:
            return hit
    return None


def _normalize(path: str) -> str:
    stack: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)
