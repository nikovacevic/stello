import pytest

from stello import config
from stello.errors import ConfigError
from stello.models import Config


@pytest.fixture(autouse=True)
def stello_home(tmp_path, monkeypatch):
    """Point STELLO_HOME at a temp dir for every test in this module."""
    monkeypatch.setenv(config.HOME_ENV_VAR, str(tmp_path))
    return tmp_path


def test_paths_respect_stello_home(stello_home):
    assert config.stello_home() == stello_home
    assert config.projects_dir() == stello_home / "projects"
    assert config.config_path() == stello_home / "config.yaml"


def test_ensure_dirs_creates_projects_dir(stello_home):
    config.ensure_dirs()
    assert config.projects_dir().is_dir()


def test_load_missing_config_returns_empty(stello_home):
    assert config.load_config() == Config(project=None)
    assert config.active_project() is None


def test_set_active_project_round_trips(stello_home):
    config.set_active_project("model")
    assert config.active_project() == "model"
    assert config.config_path().exists()


def test_save_config_writes_only_project_key(stello_home):
    config.save_config(Config(project="model"))
    text = config.config_path().read_text()
    assert "project: model" in text


def test_malformed_yaml_raises(stello_home):
    config.ensure_dirs()
    config.config_path().write_text("project: [unclosed")
    with pytest.raises(ConfigError):
        config.load_config()


def test_non_mapping_yaml_raises(stello_home):
    config.ensure_dirs()
    config.config_path().write_text("- just\n- a\n- list\n")
    with pytest.raises(ConfigError):
        config.load_config()


def test_unknown_key_raises(stello_home):
    config.ensure_dirs()
    config.config_path().write_text("project: model\nunexpected: true\n")
    with pytest.raises(ConfigError):
        config.load_config()
