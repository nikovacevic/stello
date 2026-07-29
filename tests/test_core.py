import pytest

from stello import core, paths, uv
from stello.errors import ApplicationNotFoundError

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
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "home"))


def test_add_project_and_list(make_origin):
    info = core.add_project("model", str(make_origin(manifest=MANIFEST)))
    assert info.name == "model"

    (only,) = core.list_projects()
    assert only.name == "model"


def test_apps_for_and_find_app(make_origin):
    core.add_project("model", str(make_origin(manifest=MANIFEST)))
    assert [a.name for a in core.apps_for("model")] == ["hello"]
    assert core.find_app("model", "hello").script == "./main.py"


def test_list_all_apps_spans_projects(make_origin):
    core.add_project("a", str(make_origin(manifest=MANIFEST)))
    core.add_project("b", str(make_origin(name="o2", manifest=MANIFEST)))
    refs = {f"{project}/{app.name}" for project, app in core.list_all_apps()}
    assert refs == {"a/hello", "b/hello"}


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


def test_launched_process_streams_before_exit():
    """Output must surface while the child runs, not only once it exits.

    A child whose stdout is a pipe would block-buffer its output without
    PYTHONUNBUFFERED, so a line printed (without an explicit flush) before a long
    sleep would not appear until exit — the live-log bug this guards against.
    """
    import sys
    import time

    proc = core.LaunchedProcess(
        "t", [sys.executable, "-c", "print('early'); import time; time.sleep(30)"]
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and "early" not in proc.lines():
            time.sleep(0.05)
        assert proc.lines() == ["early"]
        assert proc.is_running() is True
    finally:
        proc.stop()
        proc.wait(timeout=10)


def test_update_all_returns_names(make_origin):
    core.add_project("a", str(make_origin()))
    core.add_project("b", str(make_origin(name="o2")))
    assert core.update_all() == ["a", "b"]


def test_list_projects_carries_ref(make_origin):
    core.add_project("model", str(make_origin()))
    (only,) = core.list_projects()
    assert only.ref == "main"


def test_update_project_switches_to_ref(make_origin):
    core.add_project("model", str(make_origin(branch="beta", tag="v1.0.0")))
    assert core.current_ref("model") == "main"

    core.update_project("model", ref="beta")
    assert core.current_ref("model") == "beta"

    core.update_project("model", ref="v1.0.0")
    assert core.current_ref("model") == "v1.0.0"

    # Plain update leaves a detached pin (the tag) in place.
    core.update_project("model")
    assert core.current_ref("model") == "v1.0.0"


def test_list_refs_reports_branches_tags_and_current(make_origin):
    core.add_project("model", str(make_origin(branch="beta", tag="v1.0.0")))
    listing = core.list_refs("model")
    assert listing.current == "main"
    assert listing.branches == ["beta", "main"]
    assert listing.tags == ["v1.0.0"]
