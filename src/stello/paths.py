"""Stello's local directory layout.

Layout (macOS/Linux)::

    ~/.stello/
        projects/<name>/     # one git repo per project

Stello owns this directory. There is no active-project pointer or other global state: every
command names the project it acts on (``project/app``), so the same command always means the
same thing.

The home directory can be overridden with the ``STELLO_HOME`` environment variable, which
keeps this layer testable and lets advanced users relocate the config dir.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV_VAR = "STELLO_HOME"


def stello_home() -> Path:
    """Path to the stello home directory (``~/.stello`` by default)."""
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".stello"


def projects_dir() -> Path:
    """Path to the directory holding project git repos."""
    return stello_home() / "projects"


def ensure_dirs() -> None:
    """Create the projects directory if it doesn't exist."""
    projects_dir().mkdir(parents=True, exist_ok=True)
