"""Stello Control Plane — a NiceGUI web UI for all your stello projects.

A browser-based counterpart to the `stello` TUI, and like it, a thin view over
``stello.core``: it browses initialized projects, opens (activates) them, updates them,
and lists/launches their applications. Launched apps run as detached processes; this
scaffold reports the PID and tracks them in a simple "Running" panel (streaming logs and
richer supervision are a later phase).

Run it as a stello application:  ``stello run control-plane``  (or ``--set port=9000``).

Set STELLO_CP_NO_SHOW=1 to not auto-open a browser (used by tests).
"""

from __future__ import annotations

import argparse
import os

from nicegui import ui

from stello import core
from stello.models import ArgType

# Selected project (browse) and the processes we've launched this session.
state: dict = {"selected": None}
launched: list[core.LaunchedProcess] = []
pushed: dict[int, int] = {}       # per-process count of lines already sent to the log
alive_state: dict[int, bool] = {}  # last-seen running/exited, to refresh on change
refs: dict = {}                    # shared widget handles (the output log)


# --- actions --------------------------------------------------------------

def _select(name: str) -> None:
    state["selected"] = name
    apps_panel.refresh()


def _open(name: str) -> None:
    core.set_active(name)
    ui.notify(f"Opened '{name}' — now the active project", type="positive")
    projects_panel.refresh()


def _update(name: str) -> None:
    try:
        core.update_project(name)
        ui.notify(f"Updated '{name}'", type="positive")
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        ui.notify(str(exc), type="negative")
    apps_panel.refresh()


def _update_all() -> None:
    try:
        names = core.update_all()
    except Exception as exc:  # noqa: BLE001
        ui.notify(str(exc), type="negative")
        return
    ui.notify(f"Updated {len(names)} project(s)", type="positive")
    apps_panel.refresh()


def _launch(project: str, app, inputs: dict) -> None:
    overrides = {}
    for arg in app.args:
        widget = inputs[arg.name]
        overrides[arg.name] = (
            ("true" if widget.value else "false") if arg.type is ArgType.BOOL else str(widget.value)
        )
    try:
        proc = core.launch_supervised(project, app.name, overrides)
    except Exception as exc:  # noqa: BLE001
        ui.notify(str(exc), type="negative")
        return
    launched.append(proc)
    alive_state[id(proc)] = True
    ui.notify(f"Launched {app.name} (pid {proc.pid})", type="positive")
    running_panel.refresh()


def _stop(proc: core.LaunchedProcess) -> None:
    proc.stop()
    ui.notify(f"Stopped {proc.label}")
    running_panel.refresh()


def _tick() -> None:
    """Poll launched processes: stream new output, refresh status on change."""
    log = refs.get("log")
    status_changed = False
    for proc in launched:
        lines = proc.lines()
        seen = pushed.get(id(proc), 0)
        if log is not None and len(lines) > seen:
            for line in lines[seen:]:
                log.push(f"[{proc.label}] {line}")
            pushed[id(proc)] = len(lines)
        alive = proc.is_running()
        if alive_state.get(id(proc)) != alive:
            alive_state[id(proc)] = alive
            status_changed = True
    if status_changed:
        running_panel.refresh()


# --- panels ---------------------------------------------------------------

@ui.refreshable
def projects_panel() -> None:
    infos = core.list_projects()
    if not infos:
        ui.label("No projects initialized. Run `stello init <name> <url>`.").classes("text-gray-500")
        return
    for info in infos:
        with ui.row().classes("items-center gap-2"):
            badge = " ★" if info.is_active else ""
            ui.button(f"{info.name}{badge}", on_click=lambda n=info.name: _select(n)).props("flat")
            ui.button("Open", on_click=lambda n=info.name: _open(n)).props("outline size=sm")
            ui.button("Update", on_click=lambda n=info.name: _update(n)).props("outline size=sm")


@ui.refreshable
def apps_panel() -> None:
    name = state["selected"]
    if not name:
        ui.label("Select a project to see its applications.").classes("text-gray-500")
        return
    try:
        apps = core.apps_for(name)
    except Exception as exc:  # noqa: BLE001
        ui.label(str(exc)).classes("text-red-500")
        return
    ui.label(f"Applications in {name}").classes("text-lg font-bold")
    if not apps:
        ui.label("No applications defined in this project's stello.yaml.").classes("text-gray-500")
        return
    for app in apps:
        with ui.card().classes("w-full"):
            ui.label(app.name).classes("font-bold")
            ui.label(f"{app.dir} → {app.script}").classes("text-xs text-gray-500")
            inputs: dict = {}
            for arg in app.args:
                if arg.type is ArgType.BOOL:
                    inputs[arg.name] = ui.checkbox(arg.name, value=bool(arg.default))
                else:
                    inputs[arg.name] = ui.input(arg.name, value=str(arg.default))
            ui.button("▶ Launch", on_click=lambda a=app, i=inputs: _launch(name, a, i)).props("size=sm")


@ui.refreshable
def running_panel() -> None:
    if not launched:
        ui.label("Nothing launched yet.").classes("text-gray-500")
        return
    for proc in launched:
        alive = proc.is_running()
        with ui.row().classes("items-center gap-2"):
            ui.label(proc.label)
            ui.label("running" if alive else f"exited {proc.returncode}").classes(
                "text-green-600" if alive else "text-gray-500"
            )
            if alive:
                ui.button("Stop", on_click=lambda p=proc: _stop(p)).props("outline size=sm color=red")


def build() -> None:
    ui.label("stello · control plane").classes("text-2xl font-bold")
    with ui.row().classes("w-full no-wrap"):
        with ui.column().classes("w-1/3"):
            with ui.row().classes("items-center w-full"):
                ui.label("Projects").classes("text-lg font-bold")
                ui.button("Update all", on_click=_update_all).props("flat size=sm")
            projects_panel()
        with ui.column().classes("w-2/3"):
            apps_panel()
            ui.separator()
            ui.label("Running").classes("text-lg font-bold")
            running_panel()
            ui.label("Output").classes("text-lg font-bold")
            refs["log"] = ui.log(max_lines=500).classes("w-full h-48 bg-black text-green-400")
    ui.timer(0.7, _tick)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello control plane (web UI).")
    parser.add_argument("--port", type=int, default=8080, help="port to serve on")
    args = parser.parse_args()
    build()
    ui.run(
        port=args.port,
        title="stello control plane",
        reload=False,
        show=not os.environ.get("STELLO_CP_NO_SHOW"),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
