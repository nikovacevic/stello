import pytest

from stello import paths


@pytest.fixture(autouse=True)
def stello_home(tmp_path, monkeypatch):
    """Point STELLO_HOME at a temp dir for every test in this module."""
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path))
    return tmp_path


def test_paths_respect_stello_home(stello_home):
    assert paths.stello_home() == stello_home
    assert paths.projects_dir() == stello_home / "projects"


def test_ensure_dirs_creates_projects_dir(stello_home):
    paths.ensure_dirs()
    assert paths.projects_dir().is_dir()
