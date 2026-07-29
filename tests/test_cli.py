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


DESCRIBED_MANIFEST = """
description: Shared team apps.
applications:
  - name: hello
    description: Greets the world.
    dir: ./app
    script: ./main.py
    args:
      - name: name
        description: Who to greet.
        default: world
      - name: loud
        type: bool
        default: false
"""


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "home"))


def test_install_and_lists(make_origin):
    origin = make_origin()
    result = runner.invoke(cli.app, ["install", "model", str(origin)])
    assert result.exit_code == 0, result.output
    assert "Installed project 'model' (main)." in result.output

    listed = runner.invoke(cli.app, ["projects"])
    assert listed.exit_code == 0, listed.output
    assert "model" in listed.output
    assert "*" not in listed.output  # no active marker anymore


def test_install_at_ref(make_origin):
    origin = make_origin(branch="beta", tag="v1.0.0")
    result = runner.invoke(cli.app, ["install", "model", str(origin), "--ref", "v1.0.0"])
    assert result.exit_code == 0, result.output
    assert "Installed project 'model' (v1.0.0)." in result.output


def test_install_duplicate_errors(make_origin):
    origin = make_origin()
    runner.invoke(cli.app, ["install", "model", str(origin)])
    result = runner.invoke(cli.app, ["install", "model", str(origin)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectExistsError)


def test_apps_lists_project_slash_app(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["apps"])
    assert result.exit_code == 0, result.output
    assert "model/hello" in result.output


def test_run_invokes_uv_with_resolved_args(make_origin, monkeypatch):
    captured = {}

    def fake_run(directory, script, args):
        captured.update(directory=directory, script=script, args=args)
        return 0

    monkeypatch.setattr(uv, "run_app", fake_run)
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])

    result = runner.invoke(cli.app, ["run", "model/hello", "--set", "name=stello", "--set", "loud=true"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert captured["script"] == "./main.py"
    assert captured["args"] == ["--name", "stello", "--loud"]
    assert captured["directory"].name == "app"


def test_run_propagates_exit_code(make_origin, monkeypatch):
    monkeypatch.setattr(uv, "run_app", lambda directory, script, args: 7)
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "model/hello"])
    assert result.exit_code == 7


def test_run_requires_project_slash_app(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "hello"])  # missing project
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_run_unknown_application_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "model/ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ApplicationNotFoundError)


def test_run_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["run", "ghost/hello"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_update_requires_target(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_update_project_by_name(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "model"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (main)." in result.output


def test_update_with_ref_switches(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(branch="beta", tag="v1.0.0"))])

    result = runner.invoke(cli.app, ["update", "model", "--ref", "beta"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (beta)." in result.output

    result = runner.invoke(cli.app, ["update", "model", "--ref", "v1.0.0"])
    assert result.exit_code == 0, result.output
    assert "Updated 'model' (v1.0.0)." in result.output


def test_update_all_with_ref_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "--all", "--ref", "beta"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_projects_shows_ref(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["projects"])
    assert result.exit_code == 0, result.output
    assert "model [main]" in result.output


def test_refs_lists_and_marks_current(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(branch="beta", tag="v1.0.0"))])
    result = runner.invoke(cli.app, ["refs", "model"])
    assert result.exit_code == 0, result.output
    assert "Branches:" in result.output
    assert "* main" in result.output  # current ref marked
    assert "  beta" in result.output
    assert "Tags:" in result.output
    assert "  v1.0.0" in result.output


def test_refs_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["refs", "ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_update_all(make_origin):
    runner.invoke(cli.app, ["install", "a", str(make_origin())])
    runner.invoke(cli.app, ["install", "b", str(make_origin(name="o2"))])
    result = runner.invoke(cli.app, ["update", "--all"])
    assert result.exit_code == 0, result.output
    assert "Updated 'a'." in result.output
    assert "Updated 'b'." in result.output


def test_update_all_with_project_name_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["update", "model", "--all"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArgumentError)


def test_describe_project(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=DESCRIBED_MANIFEST))])
    result = runner.invoke(cli.app, ["describe", "model"])
    assert result.exit_code == 0, result.output
    assert "model [main]" in result.output
    assert "Shared team apps." in result.output
    assert "Applications:" in result.output
    assert "hello — Greets the world." in result.output


def test_describe_app(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=DESCRIBED_MANIFEST))])
    result = runner.invoke(cli.app, ["describe", "model/hello"])
    assert result.exit_code == 0, result.output
    assert "hello — in model [main]" in result.output
    assert "Greets the world." in result.output
    assert "dir:    ./app" in result.output
    assert "script: ./main.py" in result.output
    assert "name (string, default: world) — Who to greet." in result.output
    assert "loud (bool, default: false) — (no description)" in result.output


def test_describe_missing_description_shows_placeholder(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=APP_MANIFEST))])
    result = runner.invoke(cli.app, ["describe", "model"])
    assert result.exit_code == 0, result.output
    assert "(no description)" in result.output


def test_describe_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=DESCRIBED_MANIFEST))])
    result = runner.invoke(cli.app, ["describe", "ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_remove_deletes_project(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["remove", "model", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Removed project 'model'." in result.output
    assert "model" not in runner.invoke(cli.app, ["projects"]).output


def test_remove_confirms_before_deleting(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    # Declining at the prompt aborts and leaves the project in place.
    result = runner.invoke(cli.app, ["remove", "model"], input="n\n")
    assert result.exit_code != 0
    assert "model [main]" in runner.invoke(cli.app, ["projects"]).output


def test_remove_confirmed_deletes(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["remove", "model"], input="y\n")
    assert result.exit_code == 0, result.output
    assert "model" not in runner.invoke(cli.app, ["projects"]).output


def test_remove_unknown_project_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin())])
    result = runner.invoke(cli.app, ["remove", "ghost", "--yes"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ProjectNotFoundError)


def test_describe_unknown_app_errors(make_origin):
    runner.invoke(cli.app, ["install", "model", str(make_origin(manifest=DESCRIBED_MANIFEST))])
    result = runner.invoke(cli.app, ["describe", "model/ghost"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ApplicationNotFoundError)


def test_run_cli_reports_stello_error(monkeypatch, capsys):
    def boom():
        raise StelloError("something broke")

    monkeypatch.setattr(cli, "app", boom)
    with pytest.raises(SystemExit) as exc_info:
        cli.run_cli()
    assert exc_info.value.code == 1
    assert "something broke" in capsys.readouterr().err
