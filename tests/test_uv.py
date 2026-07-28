import subprocess
from pathlib import Path

import pytest

from stello import uv
from stello.errors import UvError


def test_run_app_builds_expected_command(monkeypatch):
    recorded = {}

    def fake_run(cmd, check=False):
        recorded["cmd"] = cmd
        recorded["check"] = check
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(uv.subprocess, "run", fake_run)

    code = uv.run_app(Path("/proj/app"), "./main.py", ["--scenario", "stress", "--verbose"])

    assert code == 0
    assert recorded["cmd"] == [
        "uv", "run", "--directory", "/proj/app",
        "./main.py", "--scenario", "stress", "--verbose",
    ]


def test_run_app_propagates_exit_code(monkeypatch):
    monkeypatch.setattr(
        uv.subprocess, "run", lambda cmd, check=False: subprocess.CompletedProcess(cmd, 3)
    )
    assert uv.run_app(Path("/proj"), "./main.py", []) == 3


def test_uv_missing_raises(monkeypatch):
    monkeypatch.setattr(uv, "UV", "uv-does-not-exist-xyz")
    with pytest.raises(UvError, match="not installed"):
        uv.run_app(Path("/proj"), "./main.py", [])
