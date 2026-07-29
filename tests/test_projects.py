import pytest

from stello import git, paths, projects
from stello.errors import (
    InvalidNameError,
    ProjectExistsError,
    ProjectNotFoundError,
    RefNotFoundError,
)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "home"))


def test_add_and_list(make_origin):
    projects.add_project("model", str(make_origin()))
    assert projects.is_project("model")
    assert projects.list_projects() == ["model"]


def test_add_at_ref(make_origin):
    projects.add_project("model", str(make_origin(branch="beta", tag="v1.0.0")), ref="beta")
    assert git.current_ref(projects.project_path("model")) == "beta"


def test_add_at_bad_ref_leaves_nothing_behind(make_origin):
    with pytest.raises(RefNotFoundError):
        projects.add_project("model", str(make_origin()), ref="nope")
    assert not projects.is_project("model")
    assert not projects.project_path("model").exists()


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


def test_remove_project_deletes_directory(make_origin):
    path = projects.add_project("model", str(make_origin()))
    assert projects.is_project("model")
    removed = projects.remove_project("model")
    assert removed == path
    assert not path.exists()
    assert projects.list_projects() == []


def test_remove_unknown_project_raises(make_origin):
    projects.add_project("model", str(make_origin()))
    with pytest.raises(ProjectNotFoundError):
        projects.remove_project("ghost")


def test_remove_rejects_traversal_name(make_origin):
    projects.add_project("model", str(make_origin()))
    with pytest.raises(InvalidNameError):
        projects.remove_project("../model")


def test_invalid_name_rejected(make_origin):
    with pytest.raises(InvalidNameError):
        projects.add_project("../evil", str(make_origin()))


def test_list_empty_when_no_projects_dir():
    assert projects.list_projects() == []
