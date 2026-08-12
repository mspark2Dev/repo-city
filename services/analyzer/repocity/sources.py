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

# github.com/o/r/tree/<rest> and gitlab.com/g/p/-/tree/<rest>, which is what the address bar
# holds when someone is looking at a branch.
WEB_BROWSE = re.compile(
    r"^(?P<repo>https?://[^/]+/[^/]+/[^/]+?)(?:\.git)?/(?:-/)?(?:tree|blob|commits?)/(?P<rest>.+)$"
)

REF_ALLOWED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

CLONE_TIMEOUT = 300.0
"""A clone that has not finished in five minutes is not going to."""

LS_REMOTE_TIMEOUT = 30.0


class SourceError(ValueError):
    """The source could not be resolved into something analyzable.

    `code` lets the client show this in the reader's language; `args[0]` stays a readable
    English sentence for logs and for codes the client does not know.
    """

    def __init__(self, message: str, code: str = "source.failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Source:
    path: Path
    kind: str  # "directory" | "clone"
    url: str | None = None
    ref: str | None = None
    subpath: str | None = None
    cloned: bool = False


def looks_like_git_url(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith(ALLOWED_SCHEMES):
        return True
    return bool(SCP_LIKE.match(candidate))


def _reject_unsafe(url: str) -> None:
    if url.startswith("-"):
        raise SourceError("a URL cannot begin with '-'", "source.invalid")
    if "::" in url.split("/")[0]:
        # ext::, and any other transport helper, can run arbitrary commands.
        raise SourceError("transport helpers such as 'ext::' are not accepted", "source.invalid")
    if not looks_like_git_url(url):
        raise SourceError(f"unsupported git URL: {url}", "source.invalid")


def clone_dir(url: str, ref: str | None = None) -> Path:
    """Each ref gets its own checkout, so switching branches never disturbs the other."""
    digest = hashlib.sha1(f"{url}#{ref or ''}".encode()).hexdigest()[:12]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", url.rstrip("/").split("/")[-1].removesuffix(".git"))
    suffix = f"-{re.sub(r'[^A-Za-z0-9._-]', '-', ref)}" if ref else ""
    return data_root() / "clones" / f"{name or 'repo'}{suffix}-{digest}"


def split_ref(value: str) -> tuple[str, str | None]:
    """`url#ref` names a branch or tag explicitly, the way pip and npm accept one."""
    base, sep, ref = value.partition("#")
    if not sep or not ref:
        return value, None
    return base, ref


def _check_ref(ref: str) -> None:
    if not REF_ALLOWED.match(ref) or ".." in ref or ref.endswith("/"):
        raise SourceError(f"not a usable branch or tag name: {ref}", "ref.invalid")


def remote_refs(url: str) -> list[str]:
    """Branch and tag names the remote advertises, longest first."""
    try:
        result = subprocess.run(  # noqa: S603 - argument list, no shell, vetted URL
            ["git", "ls-remote", "--heads", "--tags", "--", url],
            capture_output=True,
            text=True,
            timeout=LS_REMOTE_TIMEOUT,
            env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path_env()},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SourceError(f"could not read refs from {url}", "clone.unreachable") from exc

    if result.returncode != 0:
        message, code = _clone_failure(result.stderr)
        raise SourceError(message, code)

    names: list[str] = []
    for line in result.stdout.splitlines():
        _, _, ref = line.partition("\t")
        name = ref.removeprefix("refs/heads/").removeprefix("refs/tags/").removesuffix("^{}")
        if name and name != ref or ref.startswith(("refs/heads/", "refs/tags/")):
            names.append(name)
    return sorted(set(names), key=len, reverse=True)


def parse_browse_url(value: str) -> tuple[str, str] | None:
    """Split a repository browsing URL into the repo and everything after tree/blob."""
    match = WEB_BROWSE.match(value.strip())
    if match is None:
        return None
    return match.group("repo"), match.group("rest")


def _split_ref_and_path(url: str, rest: str) -> tuple[str, str | None]:
    """`tree/<rest>` mixes the ref and a subdirectory, and only the remote can separate them.

    A branch may contain slashes and so may the path after it, so the split is decided by
    asking which prefixes the remote actually publishes, longest match first.
    """
    rest = rest.strip("/")
    for candidate in remote_refs(url):
        if rest == candidate:
            return candidate, None
        if rest.startswith(f"{candidate}/"):
            return candidate, rest[len(candidate) + 1 :]
    raise SourceError(f"no branch or tag in {url} matches '{rest}'", "ref.not_found")


def resolve(value: str, *, allow_clone: bool = True) -> Source:
    candidate = value.strip()
    if not candidate:
        raise SourceError("no path or URL given", "source.empty")

    local = Path(candidate).expanduser()
    if local.is_dir():
        return Source(path=local.resolve(), kind="directory")

    url, ref = split_ref(candidate)
    subpath: str | None = None

    browsed = parse_browse_url(url)
    if browsed is not None and ref is None:
        url, rest = browsed
        _reject_unsafe(url)
        ref, subpath = _split_ref_and_path(url, rest)

    if not looks_like_git_url(url):
        raise SourceError(f"not a directory, and not a git URL: {candidate}", "source.unknown")
    if not allow_clone:
        raise SourceError("cloning is disabled", "clone.disabled")
    if ref is not None:
        _check_ref(ref)

    _reject_unsafe(url)
    destination = clone_dir(url, ref)
    cloned = False

    if not (destination / ".git").is_dir():
        # Reuse an existing checkout rather than refetching. The agent may have applied
        # changes here, and silently resetting them would be the same as losing work.
        destination.parent.mkdir(parents=True, exist_ok=True)
        _run_clone(url, destination, ref)
        cloned = True

    analyzed = destination / subpath if subpath else destination
    if not analyzed.is_dir():
        raise SourceError(f"'{subpath}' is not a directory in {url}", "subpath.not_found")

    return Source(path=analyzed, kind="clone", url=url, ref=ref, subpath=subpath, cloned=cloned)


def _run_clone(url: str, destination: Path, ref: str | None = None) -> None:
    command = ["git", "clone", "--depth", "1", "--single-branch"]
    if ref is None:
        command.append("--no-tags")
    else:
        # --branch takes a tag as readily as a branch, so both spellings work.
        command += ["--branch", ref]
    command += ["--", url, str(destination)]

    try:
        result = subprocess.run(  # noqa: S603 - argument list, no shell, vetted URL
            command,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
            # Without this a private repository makes git block on a password prompt,
            # which would hang the request instead of failing it.
            env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path_env()},
        )
    except FileNotFoundError as exc:
        raise SourceError("git is not installed", "git.missing") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"clone timed out after {CLONE_TIMEOUT:.0f}s", "clone.timeout") from exc

    if result.returncode != 0:
        _cleanup(destination)
        message, code = _clone_failure(result.stderr)
        raise SourceError(message, code)


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")


def _clone_failure(stderr: str) -> tuple[str, str]:
    text = stderr.strip().splitlines()
    detail = text[-1] if text else "clone failed"
    if "Authentication failed" in stderr or "could not read Username" in stderr:
        return (
            "clone failed: the repository is private or needs credentials git does not have",
            "clone.auth",
        )
    if "not found in upstream origin" in stderr or "Remote branch" in stderr:
        return "clone failed: that branch or tag does not exist on the remote", "ref.not_found"
    if "not found" in stderr.lower() or "Repository not found" in stderr:
        return "clone failed: repository not found", "clone.not_found"
    return f"clone failed: {detail}", "clone.failed"


def _cleanup(destination: Path) -> None:
    import shutil

    shutil.rmtree(destination, ignore_errors=True)
