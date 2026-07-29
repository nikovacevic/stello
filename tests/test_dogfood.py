"""Guards for stello dogfooding itself: the repo root is a valid stello project.

These use stello's own manifest parser (no Textual dependency), so they run in the normal
test suite and protect the wiring that lets `stello run dashboard` work.
"""

from pathlib import Path

from stello.manifest import find_application, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_root_manifest_is_valid():
    manifest = load_manifest(REPO_ROOT)
    assert find_application(manifest, "dashboard") is not None


def test_dashboard_script_exists():
    app = find_application(load_manifest(REPO_ROOT), "dashboard")
    assert app.resolved_script(REPO_ROOT).is_file()
    assert app.resolved_dir(REPO_ROOT).is_dir()
