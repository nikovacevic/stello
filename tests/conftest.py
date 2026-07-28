import subprocess

import pytest


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=Test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def make_origin(tmp_path):
    """Factory for a local git repo with a `main` branch and a stello.yaml."""

    def _make(name="origin", manifest="applications: []\n"):
        path = tmp_path / name
        path.mkdir()
        _git(path, "init", "-b", "main")
        (path / "stello.yaml").write_text(manifest)
        _git(path, "add", "-A")
        _git(path, "commit", "-m", "init")
        return path

    return _make
