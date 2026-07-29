"""Project discovery and lifecycle over ``~/.stello/projects``.

A project is a directory under the projects dir that is a valid git repository. Names are
validated before they touch the filesystem.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from stello import git, paths
from stello.errors import ProjectExistsError, ProjectNotFoundError, StelloError
from stello.naming import validate_name


def project_path(name: str) -> Path:
    """Path where project ``name`` lives (whether or not it exists)."""
    return paths.projects_dir() / name


def is_project(name: str) -> bool:
    """True if ``name`` is an initialized project (a valid git repo)."""
    return git.is_git_repo(project_path(name))


def list_projects() -> list[str]:
    """Sorted names of initialized projects."""
    root = paths.projects_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if git.is_git_repo(p))


def add_project(name: str, remote_url: str, ref: str | None = None) -> Path:
    """Clone ``remote_url`` as a new project ``name``.

    Starts on the remote's default branch, or on ``ref`` (a branch, tag, or commit) when
    given. Duplicate project names are rejected. Re-cloning the same remote under a
    different name is allowed (nothing here keys on the URL).
    """
    validate_name(name, kind="project")
    dest = project_path(name)
    if dest.exists():
        raise ProjectExistsError(f"A project named {name!r} already exists at {dest}.")
    paths.ensure_dirs()
    git.clone(remote_url, dest)
    if ref is not None:
        try:
            git.checkout_ref(dest, ref)
        except StelloError:
            # Don't leave a half-initialized project on the default branch behind.
            shutil.rmtree(dest, ignore_errors=True)
            raise
    return dest


def require_project(name: str) -> Path:
    """Return the path of project ``name``, or raise if it isn't initialized."""
    if not is_project(name):
        available = list_projects()
        hint = f" Available projects: {', '.join(available)}." if available else ""
        raise ProjectNotFoundError(f"No initialized project named {name!r}.{hint}")
    return project_path(name)


def remove_project(name: str) -> Path:
    """Delete an initialized project's directory, returning the path removed.

    The name is validated first so a traversal-style name (``../foo``) can't point
    ``rmtree`` outside the projects dir; then existence is required.
    """
    validate_name(name, kind="project")
    path = require_project(name)
    shutil.rmtree(path)
    return path
