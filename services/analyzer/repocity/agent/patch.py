"""Diff production, snapshots, and the only code in repoCity that writes to a user's file."""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..settings import data_root

SNAPSHOT_MANIFEST = "snapshot.json"


def unified_diff(original: str, proposed: str, path: str) -> str:
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    return "".join(lines)


def snapshot_dir(project_id: str, task_id: str) -> Path:
    return data_root() / "snapshots" / project_id / task_id


@dataclass(frozen=True, slots=True)
class Applied:
    snapshot_id: str
    paths: list[str]


def apply_change(project_id: str, task_id: str, root: Path, rel_path: str, content: str) -> Applied:
    """Snapshot first, then write. The snapshot is the only copy of what we overwrite."""
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"refusing to write outside the project: {rel_path}")

    destination = snapshot_dir(project_id, task_id)
    destination.mkdir(parents=True, exist_ok=True)
    backup = destination / rel_path
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)

    (destination / SNAPSHOT_MANIFEST).write_text(
        json.dumps({"root": str(root), "paths": [rel_path]}, indent=2), encoding="utf-8"
    )

    target.write_text(content, encoding="utf-8")
    return Applied(snapshot_id=f"{project_id}/{task_id}", paths=[rel_path])


def revert(snapshot_id: str) -> list[str]:
    project_id, _, task_id = snapshot_id.partition("/")
    destination = snapshot_dir(project_id, task_id)
    manifest_path = destination / SNAPSHOT_MANIFEST
    if not manifest_path.is_file():
        raise FileNotFoundError(snapshot_id)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(manifest["root"])
    restored: list[str] = []
    for rel_path in manifest["paths"]:
        backup = destination / rel_path
        if backup.is_file():
            shutil.copy2(backup, root / rel_path)
            restored.append(rel_path)
    return restored
