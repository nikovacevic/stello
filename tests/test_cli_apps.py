"""Tests for the built-in ``stello terminal`` / ``stello dashboard`` commands.

These commands launch stello's own UIs in-process, with no project required. Actually
starting a Textual/NiceGUI app needs a display/event loop, so here we verify the wiring:
the commands are registered, ``--help`` works without importing the heavy UI deps (lazy
import), and the missing-extra guard produces a friendly, install-pointing error.
"""

import importlib

import pytest
from typer.testing import CliRunner

from stello import cli
from stello.errors import MissingExtraError

runner = CliRunner()


def test_commands_are_registered():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "terminal" in result.output
    assert "dashboard" in result.output


@pytest.mark.parametrize("command", ["terminal", "dashboard"])
def test_command_help_does_not_require_extra(command, monkeypatch):
    # If --help tried to import the UI module, this would raise instead of showing help.
    def explode(_name):
        raise AssertionError("app module must not be imported for --help")

    monkeypatch.setattr(cli.importlib, "import_module", explode)
    result = runner.invoke(cli.app, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "no project required" in result.output.lower()


def test_load_app_missing_extra_raises_friendly_error(monkeypatch):
    def missing(_name):
        raise ImportError("No module named 'textual'", name="textual")

    monkeypatch.setattr(cli.importlib, "import_module", missing)
    with pytest.raises(MissingExtraError) as excinfo:
        cli._load_app("stello._apps.terminal", "terminal", "textual")
    message = str(excinfo.value)
    assert 'stello[terminal]' in message
    assert "--extra terminal" in message


def test_load_app_reraises_unrelated_import_error(monkeypatch):
    def unrelated(_name):
        raise ImportError("boom", name="some_other_dependency")

    monkeypatch.setattr(cli.importlib, "import_module", unrelated)
    with pytest.raises(ImportError) as excinfo:
        cli._load_app("stello._apps.terminal", "terminal", "textual")
    assert not isinstance(excinfo.value, MissingExtraError)


def test_load_app_returns_module_when_extra_present():
    module = cli._load_app("stello._apps.terminal", "terminal", "textual")
    assert module is importlib.import_module("stello._apps.terminal")
    assert callable(module.run)


def test_dashboard_self_launch_guard_detects_shim(tmp_path, monkeypatch):
    # The guard should refuse to launch the dashboard app (whose script imports the
    # dashboard module) but allow any other app — regardless of the app's file path.
    from stello import core
    from stello._apps import dashboard
    from stello.models import Application

    monkeypatch.setattr(core, "project_path", lambda name: tmp_path)
    (tmp_path / "main.py").write_text("from stello._apps.dashboard import main\n")
    (tmp_path / "other.py").write_text("print('hi')\n")

    dashboard_app = Application(name="stello", dir=".", script="main.py")
    other_app = Application(name="weather", dir=".", script="other.py")
    assert dashboard._would_relaunch_dashboard("stello", dashboard_app) is True
    assert dashboard._would_relaunch_dashboard("stello", other_app) is False
