import pytest
from typer.testing import CliRunner

from stello import cli, config, uv
from stello.errors import (
    ApplicationNotFoundError,
    NoActiveProjectError,
    ProjectExistsError,
    ProjectNotFoundError,
    StelloError,
)
from stello.models import Config

runner = CliRunner()

APP_MANIFEST = """
applications:
  - name: hello
    dir: ./app
    script: ./main.py
    args:
      - name: name
        default: world
      - name: loud
        type: bool
        default: false
"""


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv(config.HOME_ENV_VAR, str(tmp_path / "home"))


def test_init_activates_and_lists(make_origin):
    origin = make_origin()
    result = runner.invoke(cli.app, ["init", "model", str(origin)])
    assert result.exit_code == 0, result.output
    assert config.active_project() == "model"

    listed = runner.invoke(cli.app, ["list", "projects"])
    assert "model" in listed.output


def test_init_duplicate_errors(make_origin):
    origin = make_origin()
    runner.invoke(cli.app, ["init", "model", str(origin)])
    result = runner.invoke(cli.app, ["init", "model", str(origin)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectExistsError)


def test_open_invalid_errors():
    result = runner.invoke(cli.app, ["open", "ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_list_applications(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["list"])
    assert result.exit_code == 0, result.output
    assert "hello" in result.output


def test_run_invokes_uv_with_resolved_args(make_origin, monkeypatch):
    captured = {}

    def fake_run(directory, script, args):
        captured.update(directory=directory, script=script, args=args)
        return 0

    monkeypatch.setattr(uv, "run_app", fake_run)
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])

    result = runner.invoke(cli.app, ["run", "hello", "--set", "name=stello", "--set", "loud=true"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert captured["script"] == "./main.py"
    assert captured["args"] == ["--name", "stello", "--loud"]
    assert captured["directory"].name == "app"


def test_run_propagates_exit_code(make_origin, monkeypatch):
    monkeypatch.setattr(uv, "run_app", lambda directory, script, args: 7)
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "hello"])
    assert result.exit_code == 7


def test_run_unknown_application_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ApplicationNotFoundError)


def test_no_active_project_prompt_selects(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    config.save_config(Config(project=None))  # clear the active pointer

    result = runner.invoke(cli.app, ["list"], input="model\n")
    assert result.exit_code == 0, (result.output, result.exception)
    assert "hello" in result.output
    assert config.active_project() == "model"


def test_no_active_project_and_none_initialized_errors():
    result = runner.invoke(cli.app, ["list"])
    assert result.exit_code != 0
    assert isinstance(result.exception, NoActiveProjectError)


def test_update_all_with_project_name_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "model", "--all"])
    assert result.exit_code != 0


def test_run_cli_reports_stello_error(monkeypatch, capsys):
    def boom():
        raise StelloError("something broke")

    monkeypatch.setattr(cli, "app", boom)
    with pytest.raises(SystemExit) as exc_info:
        cli.run_cli()
    assert exc_info.value.code == 1
    assert "something broke" in capsys.readouterr().err
