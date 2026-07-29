import pytest

from stello import config, core, uv
from stello.errors import ApplicationNotFoundError, ProjectNotFoundError

MANIFEST = """
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


def test_add_project_activates_and_lists(make_origin):
    info = core.add_project("model", str(make_origin(manifest=MANIFEST)))
    assert info.is_active and info.name == "model"
    assert core.active_project() == "model"

    (only,) = core.list_projects()
    assert only.name == "model" and only.is_active is True


def test_add_project_without_activate(make_origin):
    core.add_project("a", str(make_origin()))
    core.add_project("b", str(make_origin(name="o2")), activate=False)
    assert core.active_project() == "a"
    assert {p.name: p.is_active for p in core.list_projects()} == {"a": True, "b": False}


def test_set_active_invalid_raises():
    with pytest.raises(ProjectNotFoundError):
        core.set_active("ghost")


def test_apps_for_and_find_app(make_origin):
    core.add_project("model", str(make_origin(manifest=MANIFEST)))
    assert [a.name for a in core.apps_for("model")] == ["hello"]
    assert core.find_app("model", "hello").script == "./main.py"


def test_find_app_unknown_raises(make_origin):
    core.add_project("model", str(make_origin(manifest=MANIFEST)))
    with pytest.raises(ApplicationNotFoundError):
        core.find_app("model", "ghost")


def test_command_for_builds_uv_invocation(make_origin):
    core.add_project("model", str(make_origin(manifest=MANIFEST)))
    cmd = core.command_for("model", "hello", {"name": "niko", "loud": "true"})
    assert cmd[:3] == ["uv", "run", "--directory"]
    assert cmd[-3:] == ["--name", "niko", "--loud"]
    assert cmd[4] == "./main.py"


def test_run_app_delegates_to_uv(make_origin, monkeypatch):
    core.add_project("model", str(make_origin(manifest=MANIFEST)))
    captured = {}

    def fake_run(directory, script, args):
        captured.update(directory=directory, script=script, args=args)
        return 0

    monkeypatch.setattr(uv, "run_app", fake_run)
    assert core.run_app("model", "hello", {}) == 0
    assert captured["script"] == "./main.py"
    assert captured["directory"].name == "app"
    assert captured["args"] == ["--name", "world"]  # loud False → omitted


def test_launch_app_spawns_detached(monkeypatch):
    calls = {}

    class FakeProc:
        pid = 4321

    # Mock command construction so launch_app doesn't touch git, keeping the
    # Popen patch scoped to launch_app's single spawn.
    monkeypatch.setattr(core, "command_for", lambda p, a, o: ["uv", "run", "--directory", "/x", "./m.py"])

    def fake_popen(cmd, **kwargs):
        calls.update(cmd=cmd, kwargs=kwargs)
        return FakeProc()

    monkeypatch.setattr(core.subprocess, "Popen", fake_popen)
    proc = core.launch_app("model", "hello", {"name": "x"})
    assert proc.pid == 4321
    assert calls["cmd"][:2] == ["uv", "run"]
    # detached on POSIX
    assert calls["kwargs"].get("start_new_session") is True


def test_launched_process_captures_output():
    import sys

    proc = core.LaunchedProcess("t", [sys.executable, "-c", "print('alpha'); print('beta')"])
    assert proc.wait(timeout=10) == 0
    assert proc.lines() == ["alpha", "beta"]
    assert proc.is_running() is False


def test_update_all_returns_names(make_origin):
    core.add_project("a", str(make_origin()))
    core.add_project("b", str(make_origin(name="o2")), activate=False)
    assert core.update_all() == ["a", "b"]
