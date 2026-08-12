"""Resolves what the user typed into a directory to analyze.

A local path is used as-is. A git URL is cloned into the user's data directory and the
checkout is analyzed. Nothing is ever written into a directory the user already had.

Handing a user-supplied string to `git` needs care: `ext::` and similar transports make a
URL into a command, and a value beginning with `-` is read as a flag rather than a target.
Only the transports below are accepted, and git is invoked with an argument list, never a
shell.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .settings import data_root

ALLOWED_SCHEMES = ("https://", "http://", "ssh://", "git://")
SCP_LIKE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+(:\d+)?:[^\s]+$")

CLONE_TIMEOUT = 300.0
"""A clone that has not finished in five minutes is not going to."""


class SourceError(ValueError):
    """The source could not be resolved into something analyzable."""


@dataclass(frozen=True, slots=True)
class Source:
    path: Path
    kind: str  # "directory" | "clone"
    url: str | None = None
    cloned: bool = False


def looks_like_git_url(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith(ALLOWED_SCHEMES):
        return True
    return bool(SCP_LIKE.match(candidate))


def _reject_unsafe(url: str) -> None:
    if url.startswith("-"):
        raise SourceError("a URL cannot begin with '-'")
    if "::" in url.split("/")[0]:
        # ext::, and any other transport helper, can run arbitrary commands.
        raise SourceError("transport helpers such as 'ext::' are not accepted")
    if not looks_like_git_url(url):
        raise SourceError(f"unsupported git URL: {url}")


def clone_dir(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:12]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", url.rstrip("/").split("/")[-1].removesuffix(".git"))
    return data_root() / "clones" / f"{name or 'repo'}-{digest}"


def resolve(value: str, *, allow_clone: bool = True) -> Source:
    candidate = value.strip()
    if not candidate:
        raise SourceError("no path or URL given")

    local = Path(candidate).expanduser()
    if local.is_dir():
        return Source(path=local.resolve(), kind="directory")

    if not looks_like_git_url(candidate):
        raise SourceError(f"not a directory, and not a git URL: {candidate}")
    if not allow_clone:
        raise SourceError("cloning is disabled")

    _reject_unsafe(candidate)
    destination = clone_dir(candidate)

    if (destination / ".git").is_dir():
        # Reuse an existing checkout rather than refetching. The agent may have applied
        # changes here, and silently resetting them would be the same as losing work.
        return Source(path=destination, kind="clone", url=candidate, cloned=False)

    destination.parent.mkdir(parents=True, exist_ok=True)
    _run_clone(candidate, destination)
    return Source(path=destination, kind="clone", url=candidate, cloned=True)


def _run_clone(url: str, destination: Path) -> None:
    try:
        result = subprocess.run(  # noqa: S603 - argument list, no shell, vetted URL
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                "--",
                url,
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
            # Without this a private repository makes git block on a password prompt,
            # which would hang the request instead of failing it.
            env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path_env()},
        )
    except FileNotFoundError as exc:
        raise SourceError("git is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"clone timed out after {CLONE_TIMEOUT:.0f}s") from exc

    if result.returncode != 0:
        _cleanup(destination)
        raise SourceError(_clone_message(result.stderr))


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")


def _clone_message(stderr: str) -> str:
    text = stderr.strip().splitlines()
    detail = text[-1] if text else "clone failed"
    if "Authentication failed" in stderr or "could not read Username" in stderr:
        return "clone failed: the repository is private or needs credentials git does not have"
    if "not found" in stderr.lower() or "Repository not found" in stderr:
        return "clone failed: repository not found"
    return f"clone failed: {detail}"


def _cleanup(destination: Path) -> None:
    import shutil

    shutil.rmtree(destination, ignore_errors=True)
