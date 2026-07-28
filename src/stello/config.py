"""Stello's local configuration directory and active-project pointer.

Layout (macOS/Linux)::

    ~/.stello/
        config.yaml          # active project pointer
        projects/<name>/     # one git repo per project

The home directory can be overridden with the ``STELLO_HOME`` environment variable,
which keeps this layer testable and lets advanced users relocate the config dir.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from stello.errors import ConfigError
from stello.models import Config

HOME_ENV_VAR = "STELLO_HOME"


def stello_home() -> Path:
    """Path to the stello config directory (``~/.stello`` by default)."""
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".stello"


def projects_dir() -> Path:
    """Path to the directory holding project git repos."""
    return stello_home() / "projects"


def config_path() -> Path:
    """Path to ``config.yaml``."""
    return stello_home() / "config.yaml"


def ensure_dirs() -> None:
    """Create the config and projects directories if they don't exist."""
    projects_dir().mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Load ``config.yaml``. A missing file yields an empty config (no active project)."""
    path = config_path()
    if not path.exists():
        return Config()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a YAML mapping.")
    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config at {path}:\n{exc}") from exc


def save_config(config: Config) -> None:
    """Write ``config.yaml``, creating the config directory if needed."""
    ensure_dirs()
    data = config.model_dump(exclude_none=True)
    config_path().write_text(yaml.safe_dump(data, sort_keys=False))


def active_project() -> str | None:
    """Name of the active project, or ``None`` if unset."""
    return load_config().project


def set_active_project(name: str) -> None:
    """Set the active project and persist it."""
    config = load_config()
    config.project = name
    save_config(config)
