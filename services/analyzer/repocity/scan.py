"""Repository walk: decides which files become buildings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pathspec

from .schema import Lang

LANG_BY_SUFFIX: dict[str, Lang] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".sc": "scala",
    ".m": "objectivec",
    ".mm": "objectivec",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".r": "r",
    ".R": "r",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".f90": "fortran",
    ".f95": "fortran",
    ".f03": "fortran",
    ".f": "fortran",
    ".for": "fortran",
    ".sol": "solidity",
    ".zig": "zig",
    ".vue": "vue",
    ".gd": "gdscript",
    ".sql": "plsql",
    ".pks": "plsql",
    ".pkb": "plsql",
    ".st": "smalltalk",
    ".ttcn": "ttcn",
}

DEFAULT_EXCLUDES = (
    ".git/",
    "node_modules/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "dist/",
    "build/",
    ".repocity/",
    "*.min.js",
    "*.lock",
)

# Files beyond this size are almost always generated or vendored; they would dominate the
# skyline without telling you anything about the code you write.
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class ScannedFile:
    rel_path: str
    abs_path: Path
    lang: Lang
    size: int
    mtime_ns: int


def _load_ignore_spec(root: Path, extra_excludes: tuple[str, ...]) -> pathspec.PathSpec:
    patterns = list(DEFAULT_EXCLUDES) + list(extra_excludes)
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        patterns += gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def scan(root: Path, extra_excludes: tuple[str, ...] = ()) -> list[ScannedFile]:
    """Return every analyzable file under root, sorted by path for deterministic output."""
    root = root.resolve()
    spec = _load_ignore_spec(root, extra_excludes)
    found: list[ScannedFile] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if spec.match_file(rel):
            continue
        stat = path.stat()
        if stat.st_size > MAX_FILE_BYTES:
            continue
        lang = LANG_BY_SUFFIX.get(path.suffix.lower(), "other")
        if lang == "other" and path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        found.append(
            ScannedFile(
                rel_path=rel,
                abs_path=path,
                lang=lang,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )

    return sorted(found, key=lambda f: f.rel_path)


# `other` files still get a building so the city matches the repository, but only ones
# that are plausibly source or config — not binaries.
_TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".html",
        ".css",
        ".scss",
    }
)
