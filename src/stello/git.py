"""Thin wrappers around the ``git`` commands stello needs.

All commands run as argument lists (never through a shell), so a remote URL or path can't
be interpreted as shell syntax.

A project checkout tracks a single **ref** — a branch, tag, or commit — held as git's own
HEAD. Stello keeps no separate record of it: an attached HEAD (a branch) is *tracked* and
advances to the remote tip on update; a detached HEAD (a tag or commit) is a *pin* and
stays put. ``main`` is the default a project starts on (see ``DEFAULT_BRANCH``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from stello.errors import GitError, RefNotFoundError

GIT = "git"
DEFAULT_BRANCH = "main"

# Fetch every remote branch into refs/remotes/origin/* (plus tags). Stated explicitly so it
# holds even on legacy clones whose stored remote.origin.fetch only covers ``main``.
_ALL_HEADS_REFSPEC = "+refs/heads/*:refs/remotes/origin/*"


def _git(
    *args: str, cwd: Path | None = None, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a git command. Raises ``GitError`` if git is missing.

    With ``capture=True`` (default) stdout/stderr are captured for clean error messages.
    With ``capture=False`` they are inherited, so git streams progress to the terminal.
    """
    try:
        return subprocess.run(
            [GIT, *args],
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("`git` is not installed or not on your PATH.") from exc


def is_git_repo(path: Path) -> bool:
    """Return True if ``path`` is the working tree of a git repository."""
    if not path.is_dir():
        return False
    result = _git("-C", str(path), "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def clone_main(remote_url: str, dest: Path) -> None:
    """Clone ``remote_url`` into ``dest``, checking out its ``main`` branch.

    Uses ``--branch main`` (but not ``--single-branch``), so all branches and tags come
    down and are available to switch to later, while a remote without a ``main`` branch
    still fails (an intentional requirement for now). Clone progress is streamed to the
    terminal; git prints its own error details there on failure.
    """
    result = _git(
        "clone", "--branch", DEFAULT_BRANCH, remote_url, str(dest),
        capture=False,
    )
    if result.returncode != 0:
        raise GitError(
            f"Failed to clone {remote_url} (branch {DEFAULT_BRANCH!r}). Stello requires a "
            f"remote with a `{DEFAULT_BRANCH}` branch."
        )


def fetch_all(repo: Path) -> None:
    """Fetch every branch and tag from ``origin`` into ``repo``.

    The refspec is spelled out (rather than relying on the repo's configured one) so this
    works on both new clones and older single-branch clones, making any ref checkoutable.
    """
    result = _git(
        "-C", str(repo), "fetch", "origin", _ALL_HEADS_REFSPEC, "--tags", "--prune",
    )
    if result.returncode != 0:
        raise GitError(f"git fetch failed for {repo}.\n{result.stderr.strip()}")


def current_ref(repo: Path) -> str:
    """The ref ``repo`` is currently on, for display.

    A branch name if HEAD is attached; otherwise a tag name if HEAD is exactly a tag, or a
    short commit SHA if it is a bare detached commit.
    """
    branch = _git("-C", str(repo), "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode == 0:
        return branch.stdout.strip()
    tag = _git("-C", str(repo), "describe", "--tags", "--exact-match", "HEAD")
    if tag.returncode == 0:
        return tag.stdout.strip()
    return _git("-C", str(repo), "rev-parse", "--short", "HEAD").stdout.strip()


def checkout_ref(repo: Path, ref: str) -> None:
    """Switch ``repo`` to ``ref``, discarding local drift.

    ``ref`` may be a remote branch, a tag, or a commit (resolved against the already-fetched
    refs, in that order of precedence). A branch is checked out *attached* so plain updates
    can advance it; a tag or commit is checked out *detached* as a pin. Raises
    ``RefNotFoundError`` if ``ref`` matches nothing.
    """
    _reject_option_like(ref)
    if _remote_branch_exists(repo, ref):
        result = _git("-C", str(repo), "checkout", "-f", "-B", ref, f"origin/{ref}")
    elif _tag_exists(repo, ref) or _commit_exists(repo, ref):
        result = _git("-C", str(repo), "checkout", "-f", "--detach", ref)
    else:
        raise RefNotFoundError(
            f"No branch, tag, or commit {ref!r} in this project. "
            f"Run `stello refs` to see what's available."
        )
    if result.returncode != 0:
        raise GitError(f"git checkout of {ref!r} failed for {repo}.\n{result.stderr.strip()}")


def advance_current(repo: Path) -> None:
    """Advance ``repo`` to the latest tip of its current ref, discarding local drift.

    If HEAD is attached to a branch, reset it to ``origin/<branch>``. If HEAD is detached
    (a pinned tag or commit) there is nothing to advance — the pin stays put. Assumes a
    fetch has already run.
    """
    branch = _git("-C", str(repo), "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode != 0:
        return  # detached pin — nothing to advance
    name = branch.stdout.strip()
    result = _git("-C", str(repo), "checkout", "-f", "-B", name, f"origin/{name}")
    if result.returncode != 0:
        raise GitError(f"git update of branch {name!r} failed for {repo}.\n{result.stderr.strip()}")


def list_refs(repo: Path) -> tuple[list[str], list[str]]:
    """The branches and tags available on ``origin``, each sorted.

    Read straight from the remote via ``ls-remote`` (needs no prior fetch), so newly-pushed
    refs show up immediately.
    """
    result = _git("-C", str(repo), "ls-remote", "--heads", "--tags", "origin")
    if result.returncode != 0:
        raise GitError(f"git ls-remote failed for {repo}.\n{result.stderr.strip()}")
    branches: list[str] = []
    tags: list[str] = []
    for line in result.stdout.splitlines():
        _, _, refname = line.partition("\t")
        refname = refname.strip()
        if refname.endswith("^{}"):  # peeled tag object — skip the deref line
            continue
        if refname.startswith("refs/heads/"):
            branches.append(refname[len("refs/heads/"):])
        elif refname.startswith("refs/tags/"):
            tags.append(refname[len("refs/tags/"):])
    return sorted(branches), sorted(tags)


def _remote_branch_exists(repo: Path, ref: str) -> bool:
    result = _git("-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{ref}")
    return result.returncode == 0


def _tag_exists(repo: Path, ref: str) -> bool:
    result = _git("-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/tags/{ref}")
    return result.returncode == 0


def _commit_exists(repo: Path, ref: str) -> bool:
    result = _git("-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return result.returncode == 0


def _reject_option_like(ref: str) -> None:
    """Guard against a ref that git would read as an option (e.g. ``--foo``)."""
    if ref.startswith("-"):
        raise RefNotFoundError(f"Invalid ref {ref!r}: refs cannot start with '-'.")
