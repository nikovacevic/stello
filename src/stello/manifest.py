"""Loading and validating a project's ``stello.yaml``.

The pydantic models in :mod:`stello.models` reject absolute paths and ``..`` segments in
``dir``/``script`` without needing the filesystem. This module adds the filesystem-aware
check: after resolving (which follows symlinks), every path must still live inside the
project repo — defense in depth against a manifest that tries to reach outside it.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from stello.errors import ManifestError
from stello.models import Application, Manifest

MANIFEST_FILENAME = "stello.yaml"


def _assert_within(repo_root: Path, target: Path, *, field: str, app: str) -> None:
    root = repo_root.resolve()
    if not target.is_relative_to(root):
        raise ManifestError(
            f"Application {app!r}: {field} resolves to {target}, which is outside the "
            f"project directory {root}."
        )


def load_manifest(repo_root: Path) -> Manifest:
    """Read, validate, and return the manifest for the project at ``repo_root``."""
    path = repo_root / MANIFEST_FILENAME
    if not path.exists():
        raise ManifestError(f"No {MANIFEST_FILENAME} found in project at {repo_root}.")

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"Could not parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path} must contain a YAML mapping.")

    try:
        manifest = Manifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(f"Invalid {path}:\n{exc}") from exc

    for app in manifest.applications:
        _assert_within(repo_root, app.resolved_dir(repo_root), field="dir", app=app.name)
        _assert_within(repo_root, app.resolved_script(repo_root), field="script", app=app.name)

    return manifest


def find_application(manifest: Manifest, name: str) -> Application | None:
    """Return the application with ``name``, or ``None`` if absent."""
    for app in manifest.applications:
        if app.name == name:
            return app
    return None
