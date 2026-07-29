"""Stello's UI-agnostic service layer.

One place that orchestrates the lower-level modules (``projects``, ``git``, ``manifest``,
``run``, ``uv``) into the operations a *front end* performs: browse projects, list and
launch applications, and update projects.

Stello is stateless: there is no active project. Every operation names the project it acts
on, so the same call always means the same thing.

Everything here is headless — it returns data or raises ``StelloError``; it never prints,
prompts, or otherwise assumes a particular UI. The CLI, the TUI, and the web control plane
are all thin views over this module, so behavior stays consistent across them.
"""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from stello import git, projects, run, uv
from stello.errors import ApplicationNotFoundError, ManifestError
from stello.manifest import find_application, load_manifest
from stello.models import Application


@dataclass(frozen=True)
class ProjectInfo:
    """An initialized project and where it lives on disk."""

    name: str
    path: Path


# --- projects -------------------------------------------------------------

def list_projects() -> list[ProjectInfo]:
    """All initialized projects, sorted by name."""
    return [
        ProjectInfo(name, projects.project_path(name))
        for name in projects.list_projects()
    ]


def project_path(name: str) -> Path:
    """Path of an initialized project (raises if it isn't one)."""
    return projects.require_project(name)


def add_project(name: str, remote_url: str) -> ProjectInfo:
    """Clone ``remote_url`` as project ``name``."""
    path = projects.add_project(name, remote_url)
    return ProjectInfo(name, path)


# --- applications ---------------------------------------------------------

def apps_for(project: str) -> list[Application]:
    """Applications declared in ``project``'s stello.yaml."""
    return load_manifest(projects.require_project(project)).applications


def list_all_apps() -> list[tuple[str, Application]]:
    """Every application across all projects, as ``(project, application)`` pairs.

    A project whose ``stello.yaml`` is missing or malformed is skipped rather than aborting
    the whole listing; callers that care can re-load that project to surface the error.
    """
    pairs: list[tuple[str, Application]] = []
    for name in projects.list_projects():
        try:
            apps = load_manifest(projects.project_path(name)).applications
        except ManifestError:
            continue
        pairs.extend((name, app) for app in apps)
    return pairs


def find_app(project: str, app_name: str) -> Application:
    """The named application in ``project``, or raise ``ApplicationNotFoundError``."""
    manifest = load_manifest(projects.require_project(project))
    app = find_application(manifest, app_name)
    if app is None:
        available = ", ".join(a.name for a in manifest.applications) or "(none)"
        raise ApplicationNotFoundError(
            f"No application named {app_name!r} in project {project!r}. Available: {available}."
        )
    return app


def command_for(project: str, app_name: str, overrides: dict[str, str]) -> list[str]:
    """The full ``uv run`` argv for launching ``app_name`` in ``project``."""
    app = find_app(project, app_name)
    directory = app.resolved_dir(projects.project_path(project))
    return uv.command(directory, app.script, run.resolve_args(app, overrides))


def run_app(project: str, app_name: str, overrides: dict[str, str]) -> int:
    """Run ``app_name`` in ``project`` and block until it exits (for the CLI)."""
    app = find_app(project, app_name)
    directory = app.resolved_dir(projects.project_path(project))
    return uv.run_app(directory, app.script, run.resolve_args(app, overrides))


def launch_app(project: str, app_name: str, overrides: dict[str, str]) -> subprocess.Popen:
    """Launch ``app_name`` in ``project`` as a detached process (for GUIs).

    Returns the ``Popen`` handle so a front end can track/stop it. Stdio is discarded;
    a supervising UI that wants logs should capture them itself.
    """
    cmd = command_for(project, app_name, overrides)
    return subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_detached_kwargs()
    )


def _detached_kwargs() -> dict:
    if os.name == "nt":  # pragma: no cover - exercised only on Windows
        return {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        }
    return {"start_new_session": True}


class LaunchedProcess:
    """A launched application whose output is captured for live streaming.

    Unlike :func:`launch_app` (fire-and-forget, detached), a supervised process is a child
    of the launcher: its merged stdout/stderr is pumped into a thread-safe line buffer that
    a UI can poll, and it can be stopped. Closing the supervisor ends the child.
    """

    def __init__(self, label: str, cmd: Sequence[str]) -> None:
        self.label = label
        # A child whose stdout is a pipe (not a TTY) defaults to block buffering, so its
        # output wouldn't surface until the buffer fills or it exits — making the live log
        # appear only once the app stops. PYTHONUNBUFFERED forces the child to flush each
        # line as it's written, so a supervising UI can stream output in real time.
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        self._proc = subprocess.Popen(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            with self._lock:
                self._lines.append(line.rstrip("\n"))

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    def is_running(self) -> bool:
        return self._proc.poll() is None

    def lines(self) -> list[str]:
        """A snapshot of the output captured so far."""
        with self._lock:
            return list(self._lines)

    def stop(self) -> None:
        self._proc.terminate()

    def wait(self, timeout: float | None = None) -> int:
        """Wait for exit (and for output to drain); return the exit code."""
        code = self._proc.wait(timeout=timeout)
        self._thread.join(timeout=timeout)
        return code


def launch_supervised(project: str, app_name: str, overrides: dict[str, str]) -> LaunchedProcess:
    """Launch ``app_name`` in ``project`` as a supervised child with captured output."""
    cmd = command_for(project, app_name, overrides)
    return LaunchedProcess(f"{project} · {app_name}", cmd)


# --- updates --------------------------------------------------------------

def update_project(name: str) -> None:
    """Update one project to the latest ``origin/main``."""
    git.fetch_and_reset(projects.require_project(name))


def update_all() -> list[str]:
    """Update every initialized project; return the names updated (in order)."""
    names = projects.list_projects()
    for name in names:
        git.fetch_and_reset(projects.project_path(name))
    return names
