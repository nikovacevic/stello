import subprocess

import pytest

from stello import git
from stello.errors import GitError


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=Test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def origin(tmp_path):
    """A local git repo with a `main` branch and one commit."""
    path = tmp_path / "origin"
    path.mkdir()
    _git(path, "init", "-b", "main")
    (path / "stello.yaml").write_text("applications: []\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "init")
    return path


def test_is_git_repo(tmp_path, origin):
    assert git.is_git_repo(origin) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert git.is_git_repo(plain) is False
    assert git.is_git_repo(tmp_path / "does-not-exist") is False


def test_clone_main(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone_main(str(origin), dest)
    assert git.is_git_repo(dest)
    assert (dest / "stello.yaml").exists()


def test_clone_main_requires_main_branch(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "trunk")
    (other / "f").write_text("x")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "init")

    with pytest.raises(GitError, match="main"):
        git.clone_main(str(other), tmp_path / "clone")


def test_fetch_and_reset_pulls_new_commits(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone_main(str(origin), dest)

    (origin / "new.txt").write_text("hello")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-m", "add new")

    git.fetch_and_reset(dest)
    assert (dest / "new.txt").read_text() == "hello"


def test_fetch_and_reset_discards_local_changes(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone_main(str(origin), dest)

    # Drift the working tree, as a running app might.
    (dest / "stello.yaml").write_text("applications: [tampered]\n")
    git.fetch_and_reset(dest)
    assert (dest / "stello.yaml").read_text() == "applications: []\n"


def test_git_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(git, "GIT", "git-does-not-exist-xyz")
    with pytest.raises(GitError, match="not installed"):
        git.clone_main("whatever", tmp_path / "dest")
