"""Validation for project and application names.

Names become directory names under ``~/.stello/projects`` and are interpolated into
subprocess arguments, so they're restricted to a safe character set. This prevents path
traversal (``../``), absolute paths, and other surprises.
"""

from __future__ import annotations

import re

from stello.errors import InvalidNameError

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_name(name: str, *, kind: str = "name") -> str:
    """Return ``name`` unchanged if valid, else raise ``InvalidNameError``.

    ``kind`` is used only to make the error message specific (e.g. "project").
    """
    if not _NAME_RE.match(name):
        raise InvalidNameError(
            f"Invalid {kind} {name!r}: use only letters, digits, hyphens, and underscores."
        )
    return name
