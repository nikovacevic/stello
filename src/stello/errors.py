"""Typed, user-facing errors.

`StelloError` is the base for expected failures (bad input, git/uv problems). The CLI layer
catches these, prints the message, and exits with `exit_code`. Anything that isn't a
`StelloError` is a bug and should surface as a normal traceback.
"""

from __future__ import annotations


class StelloError(Exception):
    """Base for expected, user-facing errors."""

    exit_code: int = 1


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


class RefNotFoundError(StelloError):
    """The requested git ref (branch, tag, or commit) does not exist in the project."""


class ApplicationNotFoundError(StelloError):
    """The requested application is not declared in the project's stello.yaml."""


class ArgumentError(StelloError):
    """An application argument override (`--set`), or an application reference, is invalid."""
