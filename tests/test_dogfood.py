"""Guards for stello dogfooding itself: the repo root is a valid stello project.

These use stello's own manifest parser (no Textual dependency), so they run in the normal
test suite and protect the wiring that lets `stello run terminal` work.
"""

from pathlib import Path

import pytest

from stello.manifest import find_application, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_root_manifest_is_valid():
    manifest = load_manifest(REPO_ROOT)
    names = {a.name for a in manifest.applications}
    assert {"terminal", "stello", "weather"} <= names


@pytest.mark.parametrize("name", ["terminal", "stello", "weather"])
def test_app_paths_exist(name):
    app = find_application(load_manifest(REPO_ROOT), name)
    assert app.resolved_script(REPO_ROOT).is_file()
    assert app.resolved_dir(REPO_ROOT).is_dir()
