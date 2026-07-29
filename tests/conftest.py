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
    """Factory for a local git repo with a `main` branch and a stello.yaml.

    Pass ``tag`` to tag the initial commit, and ``branch`` to add a second branch with its
    own commit — useful for exercising ref switching.
    """

    def _make(name="origin", manifest="applications: []\n", tag=None, branch=None):
        path = tmp_path / name
        path.mkdir()
        _git(path, "init", "-b", "main")
        (path / "stello.yaml").write_text(manifest)
        _git(path, "add", "-A")
        _git(path, "commit", "-m", "init")
        if tag is not None:
            _git(path, "tag", tag)
        if branch is not None:
            _git(path, "checkout", "-b", branch)
            (path / "stello.yaml").write_text(f"applications: []  # {branch}\n")
            _git(path, "commit", "-am", branch)
            _git(path, "checkout", "main")
        return path

    return _make
