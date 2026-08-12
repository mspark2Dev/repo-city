"""Per-file analysis cache.

Keyed on mtime and size rather than content hash: hashing every file costs more than the
parse it would save. The whole project lives in one JSON file — a thousand separate reads
is slower than one, and the cache is only ever read and written as a unit.

The cache lives in the user's cache directory, never inside the analyzed repository.
repoCity is pointed at other people's checkouts; leaving artifacts in them would show up
in their `git status` and is not ours to do.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def analyzer_fingerprint() -> str:
    """Hash of the analyzer's own source.

    The cache key is mtime and size, which detects edits to the *analyzed* files but not to
    the code doing the analyzing. Without this, changing how a metric is computed silently
    serves the old numbers forever — the kind of bug you only notice when a value looks
    wrong months later. Hashing the package makes the cache invalidate itself.
    """
    digest = hashlib.sha1()
    package = Path(__file__).parent
    for source in sorted(package.rglob("*.py")) + sorted(package.rglob("*.json")):
        digest.update(source.relative_to(package).as_posix().encode())
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def cache_root() -> Path:
    override = os.environ.get("REPOCITY_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "repocity"


def cache_path(root: Path) -> Path:
    digest = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]
    return cache_root() / f"{digest}.json"


@dataclass(slots=True)
class FileCache:
    path: Path
    entries: dict[str, dict[str, Any]]
    hits: int = 0
    misses: int = 0

    @classmethod
    def load(cls, root: Path) -> FileCache:
        path = cache_path(root)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path=path, entries={})

        if payload.get("analyzer") != analyzer_fingerprint():
            return cls(path=path, entries={})
        return cls(path=path, entries=payload.get("files", {}))

    def get(self, rel_path: str, mtime_ns: int, size: int) -> dict[str, Any] | None:
        entry = self.entries.get(rel_path)
        if entry is None or entry.get("mtimeNs") != mtime_ns or entry.get("size") != size:
            self.misses += 1
            return None
        self.hits += 1
        return entry["facts"]

    def put(self, rel_path: str, mtime_ns: int, size: int, facts: dict[str, Any]) -> None:
        self.entries[rel_path] = {"mtimeNs": mtime_ns, "size": size, "facts": facts}

    def prune(self, live_paths: set[str]) -> None:
        for stale in set(self.entries) - live_paths:
            del self.entries[stale]

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"analyzer": analyzer_fingerprint(), "files": self.entries}
            self.path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        except OSError:
            # A read-only checkout should still analyze, just without the speedup.
            pass
