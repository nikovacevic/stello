import pytest
from typer.testing import CliRunner

from stello import cli, paths, uv
from stello.errors import (
    ApplicationNotFoundError,
    ArgumentError,
    ProjectExistsError,
    ProjectNotFoundError,
    StelloError,
)

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
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "home"))


def test_init_and_lists(make_origin):
    origin = make_origin()
    result = runner.invoke(cli.app, ["init", "model", str(origin)])
    assert result.exit_code == 0, result.output
    assert "Initialized project 'model' (main)." in result.output

    listed = runner.invoke(cli.app, ["projects"])
    assert listed.exit_code == 0, listed.output
    assert "model" in listed.output
    assert "*" not in listed.output  # no active marker anymore


def test_init_at_ref(make_origin):
    origin = make_origin(branch="beta", tag="v1.0.0")
    result = runner.invoke(cli.app, ["init", "model", str(origin), "--ref", "v1.0.0"])
    assert result.exit_code == 0, result.output
    assert "Initialized project 'model' (v1.0.0)." in result.output


def test_init_duplicate_errors(make_origin):
    origin = make_origin()
    runner.invoke(cli.app, ["init", "model", str(origin)])
    result = runner.invoke(cli.app, ["init", "model", str(origin)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectExistsError)


def test_apps_lists_project_slash_app(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["apps"])
    assert result.exit_code == 0, result.output
    assert "model/hello" in result.output


def test_run_invokes_uv_with_resolved_args(make_origin, monkeypatch):
    captured = {}

    def fake_run(directory, script, args):
        captured.update(directory=directory, script=script, args=args)
        return 0

    monkeypatch.setattr(uv, "run_app", fake_run)
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])

    result = runner.invoke(cli.app, ["run", "model/hello", "--set", "name=stello", "--set", "loud=true"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert captured["script"] == "./main.py"
    assert captured["args"] == ["--name", "stello", "--loud"]
    assert captured["directory"].name == "app"


def test_run_propagates_exit_code(make_origin, monkeypatch):
    monkeypatch.setattr(uv, "run_app", lambda directory, script, args: 7)
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "model/hello"])
    assert result.exit_code == 7


def test_run_requires_project_slash_app(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "hello"])  # missing project
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_run_unknown_application_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "model/ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ApplicationNotFoundError)


def test_run_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "ghost/hello"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_update_requires_target(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_update_project_by_name(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "model"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (main)." in result.output


def test_update_with_ref_switches(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(branch="beta", tag="v1.0.0"))])

    result = runner.invoke(cli.app, ["update", "model", "--ref", "beta"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (beta)." in result.output

    result = runner.invoke(cli.app, ["update", "model", "--ref", "v1.0.0"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (v1.0.0)." in result.output


def test_update_all_with_ref_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "--all", "--ref", "beta"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_projects_shows_ref(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["projects"])
    assert result.exit_code == 0, result.output
    assert "model [main]" in result.output


def test_refs_lists_and_marks_current(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin(branch="beta", tag="v1.0.0"))])
    result = runner.invoke(cli.app, ["refs", "model"])
    assert result.exit_code == 0, result.output
    assert "Branches:" in result.output
    assert "* main" in result.output  # current ref marked
    assert "  beta" in result.output
    assert "Tags:" in result.output
    assert "  v1.0.0" in result.output


def test_refs_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["refs", "ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_update_all(make_origin):
    runner.invoke(cli.app, ["init", "a", str(make_origin())])
    runner.invoke(cli.app, ["init", "b", str(make_origin(name="o2"))])
    result = runner.invoke(cli.app, ["update", "--all"])
    assert result.exit_code == 0, result.output
    assert "Updated 'a'." in result.output
    assert "Updated 'b'." in result.output


def test_update_all_with_project_name_errors(make_origin):
    runner.invoke(cli.app, ["init", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "model", "--all"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_run_cli_reports_stello_error(monkeypatch, capsys):
    def boom():
        raise StelloError("something broke")

    monkeypatch.setattr(cli, "app", boom)
    with pytest.raises(SystemExit) as exc_info:
        cli.run_cli()
    assert exc_info.value.code == 1
    assert "something broke" in capsys.readouterr().err
