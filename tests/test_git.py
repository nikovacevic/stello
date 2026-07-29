import subprocess

import pytest

from stello import git
from stello.errors import GitError, RefNotFoundError


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
    """A local git repo with a `main` branch, a `beta` branch, and a `v1.0.0` tag."""
    path = tmp_path / "origin"
    path.mkdir()
    _git(path, "init", "-b", "main")
    (path / "stello.yaml").write_text("applications: []\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "init")
    _git(path, "tag", "v1.0.0")
    _git(path, "checkout", "-b", "beta")
    (path / "stello.yaml").write_text("applications: []  # beta\n")
    _git(path, "commit", "-am", "beta")
    _git(path, "checkout", "main")
    return path


def _rev(path, ref="HEAD"):
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", ref],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def test_is_git_repo(tmp_path, origin):
    assert git.is_git_repo(origin) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert git.is_git_repo(plain) is False
    assert git.is_git_repo(tmp_path / "does-not-exist") is False


def test_clone(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    assert git.is_git_repo(dest)
    assert (dest / "stello.yaml").exists()


def test_clone_uses_remote_default_branch(tmp_path):
    """A remote whose default branch isn't `main` clones onto that branch."""
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "trunk")
    (other / "f").write_text("x")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "init")

    dest = tmp_path / "clone"
    git.clone(str(other), dest)
    assert git.current_ref(dest) == "trunk"


def test_advance_current_pulls_new_commits(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)

    (origin / "new.txt").write_text("hello")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-m", "add new")

    git.fetch_all(dest)
    git.advance_current(dest)
    assert (dest / "new.txt").read_text() == "hello"


def test_advance_current_discards_local_changes(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)

    # Drift the working tree, as a running app might.
    (dest / "stello.yaml").write_text("applications: [tampered]\n")
    git.fetch_all(dest)
    git.advance_current(dest)
    assert (dest / "stello.yaml").read_text() == "applications: []\n"


def test_clone_checks_out_default_branch(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    assert git.current_ref(dest) == "main"


def test_checkout_branch_is_attached_and_tracked(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    git.fetch_all(dest)
    git.checkout_ref(dest, "beta")
    assert git.current_ref(dest) == "beta"
    assert (dest / "stello.yaml").read_text() == "applications: []  # beta\n"

    # A branch is attached, so a later advance follows new commits on origin/beta.
    _git(origin, "checkout", "beta")
    (origin / "b.txt").write_text("more")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-m", "beta more")
    _git(origin, "checkout", "main")
    git.fetch_all(dest)
    git.advance_current(dest)
    assert (dest / "b.txt").read_text() == "more"


def test_checkout_tag_is_a_detached_pin(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    git.fetch_all(dest)
    git.checkout_ref(dest, "v1.0.0")
    assert git.current_ref(dest) == "v1.0.0"

    # A detached pin does not move, even when origin/main advances.
    pinned = _rev(dest)
    (origin / "new.txt").write_text("hello")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-m", "add new")
    git.fetch_all(dest)
    git.advance_current(dest)
    assert _rev(dest) == pinned


def test_checkout_commit_is_detached(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    git.fetch_all(dest)
    sha = _rev(origin, "beta")  # an untagged commit
    git.checkout_ref(dest, sha)
    assert git.current_ref(dest) == sha[:7]


def test_checkout_unknown_ref_raises(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    git.fetch_all(dest)
    with pytest.raises(RefNotFoundError, match="nope"):
        git.checkout_ref(dest, "nope")


def test_checkout_rejects_option_like_ref(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    with pytest.raises(RefNotFoundError, match="cannot start with"):
        git.checkout_ref(dest, "--force")


def test_list_refs(tmp_path, origin):
    dest = tmp_path / "clone"
    git.clone(str(origin), dest)
    branches, tags = git.list_refs(dest)
    assert branches == ["beta", "main"]
    assert tags == ["v1.0.0"]


def test_git_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(git, "GIT", "git-does-not-exist-xyz")
    with pytest.raises(GitError, match="not installed"):
        git.clone("whatever", tmp_path / "dest")
