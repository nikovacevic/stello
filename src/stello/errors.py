"""Typed, user-facing errors.

`StelloError` is the base for expected failures (bad input, missing config, git/uv
problems). The CLI layer catches these, prints the message, and exits with `exit_code`.
Anything that isn't a `StelloError` is a bug and should surface as a normal traceback.
"""

from __future__ import annotations


class StelloError(Exception):
    """Base for expected, user-facing errors."""

    exit_code: int = 1


class ConfigError(StelloError):
    """The stello config directory or config.yaml is missing, malformed, or invalid."""


class InvalidNameError(StelloError):
    """A project or application name contains disallowed characters."""


class ManifestError(StelloError):
    """A project's stello.yaml is missing, malformed, or invalid."""


class GitError(StelloError):
    """A git command failed, or git is not installed."""


class UvError(StelloError):
    """A uv command failed, or uv is not installed."""


class ProjectExistsError(StelloError):
    """A project with the requested name already exists."""


class ProjectNotFoundError(StelloError):
    """The requested project is not an initialized project."""


class NoActiveProjectError(StelloError):
    """A command needs a project, but none is active and none could be selected."""


class ApplicationNotFoundError(StelloError):
    """The requested application is not declared in the active project's stello.yaml."""


class ArgumentError(StelloError):
    """An application argument override (`--set`) is malformed or invalid."""


class MissingExtraError(StelloError):
    """A built-in UI command needs an optional extra that isn't installed."""
