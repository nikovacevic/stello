"""Thin wrappers around the ``git`` commands stello needs.

All commands run as argument lists (never through a shell), so a remote URL or path can't
be interpreted as shell syntax. Stello only ever works with the ``main`` branch (see
product.md); branches/tags are a future concern.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from stello.errors import GitError

GIT = "git"
DEFAULT_BRANCH = "main"


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
    """Clone ``remote_url``'s ``main`` branch into ``dest``.

    Uses ``--branch main --single-branch``, so a remote without a ``main`` branch fails
    (that is an intentional requirement for now). Clone progress is streamed to the
    terminal; git prints its own error details there on failure.
    """
    result = _git(
        "clone", "--branch", DEFAULT_BRANCH, "--single-branch", remote_url, str(dest),
        capture=False,
    )
    if result.returncode != 0:
        raise GitError(
            f"Failed to clone {remote_url} (branch {DEFAULT_BRANCH!r}). Stello requires a "
            f"remote with a `{DEFAULT_BRANCH}` branch."
        )


def fetch_and_reset(repo: Path) -> None:
    """Update ``repo`` to the latest ``origin/main``.

    Project checkouts are treated as read-only mirrors, so this fetches and then hard-resets
    rather than merging — a drifted working tree is discarded, not conflicted.
    """
    fetch = _git("-C", str(repo), "fetch", "origin", DEFAULT_BRANCH)
    if fetch.returncode != 0:
        raise GitError(f"git fetch failed for {repo}.\n{fetch.stderr.strip()}")
    reset = _git("-C", str(repo), "reset", "--hard", f"origin/{DEFAULT_BRANCH}")
    if reset.returncode != 0:
        raise GitError(f"git reset failed for {repo}.\n{reset.stderr.strip()}")
