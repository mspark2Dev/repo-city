"""Source resolution runs git against a string the user typed, so its guards matter."""

from __future__ import annotations

import pytest

from repocity.sources import SourceError, clone_dir, looks_like_git_url, resolve


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo.git",
        "http://example.com/owner/repo",
        "ssh://git@github.com:22/owner/repo.git",
        "git://example.com/repo",
        "git@github.com:owner/repo.git",
        "git@gitlab.example.com:group/sub/repo.git",
    ],
)
def test_recognized_git_urls(url: str):
    assert looks_like_git_url(url)


@pytest.mark.parametrize(
    "value",
    ["/tmp", "./relative", "not a url", "", "repo.git", "ext::sh -c whoami"],
)
def test_values_that_are_not_git_urls(value: str):
    assert not looks_like_git_url(value)


@pytest.mark.parametrize(
    "hostile",
    [
        "ext::sh -c 'touch /tmp/pwned'",
        "--upload-pack=touch /tmp/pwned",
        "-u attacker",
        "file:///etc/passwd",
    ],
)
def test_hostile_sources_are_refused(hostile: str, tmp_path, monkeypatch):
    """`ext::` turns a URL into a command, and a leading dash turns it into a flag."""
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(SourceError):
        resolve(hostile)


def test_an_existing_directory_is_used_as_is(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path / "state"))
    project = tmp_path / "project"
    project.mkdir()
    source = resolve(str(project))
    assert source.kind == "directory"
    assert source.path == project.resolve()
    assert not source.cloned


def test_a_missing_path_that_is_not_a_url_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(SourceError, match="not a directory"):
        resolve(str(tmp_path / "nope"))


def test_cloning_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(SourceError, match="cloning is disabled"):
        resolve("https://github.com/owner/repo.git", allow_clone=False)


def test_clone_directory_is_stable_and_named_after_the_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    first = clone_dir("https://github.com/pallets/click.git")
    assert first == clone_dir("https://github.com/pallets/click.git")
    assert first.name.startswith("click-")
    assert first.parent == tmp_path / "clones"


def test_different_urls_do_not_share_a_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    assert clone_dir("https://github.com/a/repo.git") != clone_dir("https://gitlab.com/a/repo.git")


def test_an_existing_checkout_is_reused_rather_than_refetched(tmp_path, monkeypatch):
    """A clone the agent has edited must not be silently reset."""
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    url = "https://github.com/owner/repo.git"
    destination = clone_dir(url)
    (destination / ".git").mkdir(parents=True)

    source = resolve(url)
    assert source.path == destination
    assert source.kind == "clone"
    assert not source.cloned


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://host/o/r.git#develop", ("https://host/o/r.git", "develop")),
        ("https://host/o/r.git", ("https://host/o/r.git", None)),
        ("https://host/o/r.git#", ("https://host/o/r.git#", None)),
    ],
)
def test_a_fragment_names_a_ref(value: str, expected: tuple[str, str | None]):
    from repocity.sources import split_ref

    assert split_ref(value) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/o/r/tree/stable", ("https://github.com/o/r", "stable")),
        ("https://github.com/o/r/tree/main/src", ("https://github.com/o/r", "main/src")),
        ("https://gitlab.com/g/p/-/tree/release", ("https://gitlab.com/g/p", "release")),
        ("https://github.com/o/r/blob/main/a.py", ("https://github.com/o/r", "main/a.py")),
        ("https://github.com/o/r.git", None),
        ("https://github.com/o/r", None),
    ],
)
def test_browsing_urls_split_into_repo_and_remainder(url: str, expected):
    from repocity.sources import parse_browse_url

    assert parse_browse_url(url) == expected


def test_each_ref_gets_its_own_checkout(tmp_path, monkeypatch):
    """Switching branches must not disturb the checkout the other branch is using."""
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    url = "https://github.com/o/r.git"
    assert clone_dir(url, "main") != clone_dir(url, "develop")
    assert clone_dir(url, None) != clone_dir(url, "main")
    assert "develop" in clone_dir(url, "develop").name


@pytest.mark.parametrize("ref", ["-x", "a..b", "feature/", "with space", ""])
def test_unusable_refs_are_refused(ref: str, tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(SourceError):
        resolve(f"https://github.com/o/r.git#{ref}" if ref else "https://github.com/o/r.git#")


def test_errors_carry_a_code_for_the_interface_to_translate(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOCITY_DATA_DIR", str(tmp_path))
    with pytest.raises(SourceError) as caught:
        resolve("ext::sh -c whoami")
    assert caught.value.code == "source.unknown"
