"""Guards for stello running its own control panels as ordinary projects.

The repo root is itself a valid stello project: its ``stello.yaml`` declares the ``terminal``
and ``dashboard`` apps, so ``stello run stello/terminal`` (and ``.../dashboard``) work once
the repo is initialized as a project. These checks use stello's own manifest parser (no
Textual/NiceGUI dependency), so they run in the normal test suite.
"""

from pathlib import Path

import pytest

from stello.manifest import find_application, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_root_manifest_is_valid():
    manifest = load_manifest(REPO_ROOT)
    names = {a.name for a in manifest.applications}
    assert {"terminal", "dashboard"} <= names


@pytest.mark.parametrize("name", ["terminal", "dashboard"])
def test_app_paths_exist(name):
    app = find_application(load_manifest(REPO_ROOT), name)
    assert app.resolved_script(REPO_ROOT).is_file()
    assert app.resolved_dir(REPO_ROOT).is_dir()
