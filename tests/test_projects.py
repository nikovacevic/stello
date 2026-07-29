import pytest

from stello import paths, projects
from stello.errors import InvalidNameError, ProjectExistsError, ProjectNotFoundError


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "home"))


def test_add_and_list(make_origin):
    projects.add_project("model", str(make_origin()))
    assert projects.is_project("model")
    assert projects.list_projects() == ["model"]


def test_duplicate_name_blocked(make_origin):
    origin = make_origin()
    projects.add_project("model", str(origin))
    with pytest.raises(ProjectExistsError):
        projects.add_project("model", str(origin))


def test_reclone_under_different_name(make_origin):
    origin = make_origin()
    projects.add_project("model", str(origin))
    projects.add_project("model-copy", str(origin))
    assert projects.list_projects() == ["model", "model-copy"]


def test_require_missing_project_raises():
    with pytest.raises(ProjectNotFoundError):
        projects.require_project("ghost")


def test_invalid_name_rejected(make_origin):
    with pytest.raises(InvalidNameError):
        projects.add_project("../evil", str(make_origin()))


def test_list_empty_when_no_projects_dir():
    assert projects.list_projects() == []
