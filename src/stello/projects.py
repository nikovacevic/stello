"""Project discovery and lifecycle over ``~/.stello/projects``.

A project is a directory under the projects dir that is a valid git repository. Names are
validated before they touch the filesystem.
"""

from __future__ import annotations

from pathlib import Path

from stello import config, git
from stello.errors import ProjectExistsError, ProjectNotFoundError
from stello.naming import validate_name


def project_path(name: str) -> Path:
    """Path where project ``name`` lives (whether or not it exists)."""
    return config.projects_dir() / name


def is_project(name: str) -> bool:
    """True if ``name`` is an initialized project (a valid git repo)."""
    return git.is_git_repo(project_path(name))


def list_projects() -> list[str]:
    """Sorted names of initialized projects."""
    root = config.projects_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if git.is_git_repo(p))


def add_project(name: str, remote_url: str) -> Path:
    """Clone ``remote_url`` as a new project ``name``.

    Duplicate project names are rejected. Re-cloning the same remote under a different name
    is allowed (nothing here keys on the URL).
    """
    validate_name(name, kind="project")
    dest = project_path(name)
    if dest.exists():
        raise ProjectExistsError(f"A project named {name!r} already exists at {dest}.")
    config.ensure_dirs()
    git.clone_main(remote_url, dest)
    return dest


def require_project(name: str) -> Path:
    """Return the path of project ``name``, or raise if it isn't initialized."""
    if not is_project(name):
        available = list_projects()
        hint = f" Available projects: {', '.join(available)}." if available else ""
        raise ProjectNotFoundError(f"No initialized project named {name!r}.{hint}")
    return project_path(name)
