"""Stello Dashboard — a NiceGUI web control panel for all your stello projects.

A browser-based counterpart to the `terminal` TUI, and like it, a thin view over
``stello.core``: it browses initialized projects (left pane), lists the applications in
whichever project you're browsing (middle pane), and opens an application into a run pane
(right) that is split between its argument controls and a live log.

It deliberately mirrors the TUI's feel:

- three panes, monospace text, a light and a dark theme;
- arrow keys move the highlight within the focused pane, Tab / Shift+Tab switch panes,
  and the focused pane is outlined so you can see where you are;
- Enter (or a click) on a project *opens* it — the same effect as ``stello open`` — and on
  an application *opens it into the run pane*;
- the run pane's Start button launches the app as a supervised child (via
  ``core.launch_supervised``) and streams its output; Exit terminates it.

Browsing with the arrow keys is non-destructive: it only previews a project's apps. Only
Enter/click on a project changes the active one.

Run it as a stello application:  ``stello run stello``  (or ``--set port=9000``).

Set STELLO_CP_NO_SHOW=1 to not auto-open a browser (used by tests).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from nicegui import ui

from stello import core
from stello.models import Application, ArgType

SELF_SCRIPT = Path(__file__).resolve()

# The three panes, in Tab order.
PANES = ("projects", "apps", "run")

# Shared, single-user state (this panel, like the TUI, drives one machine).
state: dict = {
    "focus": "projects",       # which pane is active: one of PANES
    "proj_sel": 0,             # highlighted row in the projects pane
    "app_sel": 0,              # highlighted row in the apps pane
    "project": None,           # name of the browsed project (drives the apps pane)
    "apps": [],                # Applications in the browsed project
    "load_error": None,        # manifest error for the browsed project, if any
    "app": None,               # Application opened into the run pane
    "app_inputs": {},          # arg name -> input/checkbox widget (current render)
    "proc": None,              # LaunchedProcess for the opened app, if started
    "proc_alive": None,        # last-seen running state, to refresh buttons on change
    "log_pushed": 0,           # lines of the opened proc already pushed to the log
}
procs: dict[str, core.LaunchedProcess] = {}   # label -> most recent launch
refs: dict = {}                               # persistent widget handles (log, dark_mode)


def _args_summary(app: Application) -> str:
    if not app.args:
        return "(no args)"
    return ", ".join(f"{a.name}:{a.type.value}={a.default}" for a in app.args)


def _label_for(project: str, app: Application) -> str:
    return f"{project} · {app.name}"


# --- browsing / opening ---------------------------------------------------

def _load_project(name: str | None) -> None:
    """Populate state for a browsed project (no widget refresh — safe before the loop)."""
    state["project"] = name
    state["app_sel"] = 0
    if name is None:
        state["apps"] = []
        state["load_error"] = None
    else:
        try:
            state["apps"] = core.apps_for(name)
            state["load_error"] = None
        except Exception as exc:  # noqa: BLE001 - surface manifest problems, don't crash
            state["apps"] = []
            state["load_error"] = str(exc)


def _browse(name: str | None) -> None:
    """Preview a project's applications without making it active (runtime handler)."""
    _load_project(name)
    apps_panel.refresh()
    _refresh_bar()


def _open_project(name: str) -> None:
    """Make ``name`` the active project (Enter/click on a project row)."""
    try:
        core.set_active(name)
    except Exception as exc:  # noqa: BLE001
        ui.notify(str(exc), type="negative")
        return
    _browse(name)
    projects_panel.refresh()
    ui.notify(f"Opened '{name}' — now the active project", type="positive")


def _open_app(app: Application) -> None:
    """Load an application into the run pane (Enter/click on an app row)."""
    state["app"] = app
    # Reconnect to this app's most recent launch (running or exited) so its log shows.
    proc = procs.get(_label_for(state["project"], app))
    state["proc"] = proc
    state["proc_alive"] = proc.is_running() if proc else None
    run_panel.refresh()  # rebuilds the log from this app's captured output


# --- run: start / stop / stream ------------------------------------------

def _collect_overrides(app: Application) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for arg in app.args:
        widget = state["app_inputs"].get(arg.name)
        if widget is None:
            continue
        overrides[arg.name] = (
            ("true" if widget.value else "false") if arg.type is ArgType.BOOL else str(widget.value)
        )
    return overrides


def _start() -> None:
    app, project = state["app"], state["project"]
    if app is None or project is None:
        return
    label = _label_for(project, app)
    existing = procs.get(label)
    if existing and existing.is_running():
        ui.notify(f"{app.name} is already running", type="warning")
        return

    # Mirror the TUI: refuse to launch the dashboard from itself.
    try:
        if app.resolved_script(core.project_path(project)) == SELF_SCRIPT:
            ui.notify("Refusing to launch the dashboard from itself", type="warning")
            return
    except Exception:  # noqa: BLE001 - if we can't tell, fall through and let it try
        pass

    try:
        proc = core.launch_supervised(project, app.name, _collect_overrides(app))
    except Exception as exc:  # noqa: BLE001
        ui.notify(str(exc), type="negative")
        return

    procs[label] = proc
    state["proc"] = proc
    state["proc_alive"] = True
    state["log_pushed"] = 0
    ui.notify(f"Started {app.name} (pid {proc.pid})", type="positive")
    run_panel.refresh()  # rebuilds an empty log for the fresh process


def _exit() -> None:
    proc = state["proc"]
    if proc is None or not proc.is_running():
        return
    proc.stop()
    ui.notify(f"Exiting {proc.label}")
    run_panel.refresh()


def _tick() -> None:
    """Poll the opened process: stream new output and flip buttons on state change."""
    proc = state["proc"]
    if proc is None:
        return
    log = refs.get("log")
    lines = proc.lines()
    seen = state["log_pushed"]
    if log is not None and len(lines) > seen:
        for line in lines[seen:]:
            log.push(line)
        state["log_pushed"] = len(lines)
    alive = proc.is_running()
    if state["proc_alive"] != alive:
        state["proc_alive"] = alive
        run_panel.refresh()  # rebuilds the log (incl. the exit marker) and buttons


# --- keyboard navigation --------------------------------------------------

def _set_focus(pane: str) -> None:
    state["focus"] = pane
    projects_panel.refresh()
    apps_panel.refresh()
    run_panel.refresh()


def _cycle_focus(delta: int) -> None:
    idx = (PANES.index(state["focus"]) + delta) % len(PANES)
    _set_focus(PANES[idx])


def _move(delta: int) -> None:
    focus = state["focus"]
    if focus == "projects":
        infos = core.list_projects()
        if not infos:
            return
        state["proj_sel"] = max(0, min(len(infos) - 1, state["proj_sel"] + delta))
        _browse(infos[state["proj_sel"]].name)
        projects_panel.refresh()
    elif focus == "apps":
        apps = state["apps"]
        if not apps:
            return
        state["app_sel"] = max(0, min(len(apps) - 1, state["app_sel"] + delta))
        apps_panel.refresh()


def _activate() -> None:
    focus = state["focus"]
    if focus == "projects":
        infos = core.list_projects()
        if infos:
            _open_project(infos[state["proj_sel"]].name)
    elif focus == "apps":
        apps = state["apps"]
        if apps:
            _open_app(apps[state["app_sel"]])


def _on_key(e) -> None:
    if not e.action.keydown:
        return
    if e.key.tab:
        _cycle_focus(-1 if e.modifiers.shift else 1)
    elif e.key.arrow_down:
        _move(1)
    elif e.key.arrow_up:
        _move(-1)
    elif e.key.enter:
        _activate()


# --- panes ----------------------------------------------------------------

def _row_classes(selected: bool, focused_pane: bool) -> str:
    base = "row-item"
    if selected and focused_pane:
        return f"{base} row-sel"
    if selected:
        return f"{base} row-sel-dim"
    return base


@ui.refreshable
def projects_panel() -> None:
    focused = state["focus"] == "projects"
    with ui.element("div").classes("pane " + ("pane-active" if focused else "")):
        ui.label("Projects  (Enter: open)").classes("pane-title")
        infos = core.list_projects()
        if not infos:
            ui.label("No projects. Run `stello init <name> <url>`.").classes("pane-empty")
            return
        state["proj_sel"] = max(0, min(len(infos) - 1, state["proj_sel"]))
        with ui.element("div").classes("pane-body"):
            for i, info in enumerate(infos):
                marker = "*" if info.is_active else " "
                row = ui.element("div").classes(_row_classes(i == state["proj_sel"], focused))
                row.on("click", lambda n=info.name, idx=i: (_focus_select("projects", idx), _open_project(n)))
                with row:
                    ui.label(f"{marker} {info.name}")


@ui.refreshable
def apps_panel() -> None:
    focused = state["focus"] == "apps"
    with ui.element("div").classes("pane " + ("pane-active" if focused else "")):
        ui.label("Applications").classes("pane-title")
        if state["project"] is None:
            ui.label("Select a project to see its applications.").classes("pane-empty")
            return
        if state["load_error"]:
            ui.label(state["load_error"]).classes("pane-empty pane-error")
            return
        apps = state["apps"]
        if not apps:
            ui.label("No applications in this project's stello.yaml.").classes("pane-empty")
            return
        state["app_sel"] = max(0, min(len(apps) - 1, state["app_sel"]))
        with ui.element("div").classes("pane-body"):
            with ui.element("div").classes("app-row app-head"):
                for col in ("app", "dir", "script", "args"):
                    ui.label(col)
            for i, app in enumerate(apps):
                row = ui.element("div").classes("app-row " + _row_classes(i == state["app_sel"], focused))
                row.on("click", lambda a=app, idx=i: (_focus_select("apps", idx), _open_app(a)))
                with row:
                    ui.label(app.name)
                    ui.label(app.dir)
                    ui.label(app.script)
                    ui.label(_args_summary(app))


@ui.refreshable
def run_panel() -> None:
    focused = state["focus"] == "run"
    with ui.element("div").classes("pane pane-run " + ("pane-active" if focused else "")):
        app = state["app"]
        # Top half: detail, argument controls, Start/Exit.
        with ui.element("div").classes("run-top"):
            if app is None:
                ui.label("Open an application to run it.").classes("pane-empty")
            else:
                ui.label(app.name).classes("run-title")
                ui.label(f"{app.dir} → {app.script}").classes("run-sub")
                state["app_inputs"] = {}
                with ui.element("div").classes("arg-controls"):
                    for arg in app.args:
                        with ui.element("div").classes("arg-row"):
                            ui.label(arg.name).classes("arg-label")
                            if arg.type is ArgType.BOOL:
                                state["app_inputs"][arg.name] = ui.checkbox(value=bool(arg.default))
                            else:
                                state["app_inputs"][arg.name] = (
                                    ui.input(value=str(arg.default)).props("dense outlined").classes("arg-input")
                                )
                running = bool(state["proc"] and state["proc"].is_running())
                with ui.element("div").classes("run-buttons"):
                    ui.button("▶ Start", on_click=_start).props(
                        "unelevated color=positive" + (" disable" if running else "")
                    )
                    ui.button("■ Exit", on_click=_exit).props(
                        "outline color=negative" + ("" if running else " disable")
                    )
        # Bottom half: live log. Rebuilt on each refresh (open / status change) and
        # re-filled from the process's captured output; _tick appends new lines between
        # refreshes.
        log = ui.log(max_lines=1000).classes("run-log")
        refs["log"] = log
        proc = state["proc"]
        lines = proc.lines() if proc else []
        for line in lines:
            log.push(line)
        state["log_pushed"] = len(lines)
        if proc is not None and not proc.is_running():
            log.push(f"(exited {proc.returncode})")


# --- click helpers --------------------------------------------------------

def _focus_select(pane: str, idx: int) -> None:
    """A click both focuses a pane and selects the clicked row."""
    state["focus"] = pane
    if pane == "projects":
        state["proj_sel"] = idx
    else:
        state["app_sel"] = idx
    projects_panel.refresh()
    apps_panel.refresh()
    run_panel.refresh()


# --- theme / layout -------------------------------------------------------

CSS = """
* { font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace !important; }
.material-icons, .material-icons-outlined, .q-icon { font-family: 'Material Icons' !important; }
:root {
  --bg:#f6f6f6; --fg:#1c1c1c; --muted:#6b7280; --border:#d0d0d0;
  --pane-bg:#ffffff; --accent:#1e66f5; --accent-fg:#ffffff;
  --hover:rgba(0,0,0,.05); --sel-dim:rgba(0,0,0,.08);
  --bar-bg:#ececec; --log-bg:#0b0b0b; --log-fg:#4ade80;
}
body.body--dark {
  --bg:#0d0d0d; --fg:#e5e5e5; --muted:#9ca3af; --border:#2f2f2f;
  --pane-bg:#141414; --accent:#3b82f6; --accent-fg:#ffffff;
  --hover:rgba(255,255,255,.06); --sel-dim:rgba(255,255,255,.10);
  --bar-bg:#161616; --log-bg:#000000; --log-fg:#4ade80;
}
body { background:var(--bg); color:var(--fg); }
.bar { background:var(--bar-bg); border-bottom:1px solid var(--border);
       padding:6px 12px; display:flex; align-items:center; gap:12px; }
.bar-title { font-weight:700; }
.bar-sub { color:var(--muted); }
.bar-spacer { flex:1; }
.footer { background:var(--bar-bg); border-top:1px solid var(--border);
          padding:4px 12px; color:var(--muted); font-size:.8rem; }
.pane { background:var(--pane-bg); border:1px solid var(--border); border-radius:6px;
        margin:6px; display:flex; flex-direction:column; flex:1 1 auto; min-height:0; overflow:hidden; }
.pane-active { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }
.pane-title { color:var(--muted); font-weight:700; padding:4px 8px;
              border-bottom:1px solid var(--border); }
.pane-body { flex:1; min-height:0; overflow:auto; padding:2px 0; }
.pane-empty { color:var(--muted); padding:8px; }
.pane-error { color:#ef4444; }
.row-item { padding:2px 8px; cursor:pointer; white-space:pre; }
.row-item:hover { background:var(--hover); }
.row-sel { background:var(--accent); color:var(--accent-fg); }
.row-sel-dim { background:var(--sel-dim); }
.app-row { display:grid; grid-template-columns:1.2fr 1.4fr 1fr 2fr; gap:8px; }
.app-head { color:var(--muted); font-weight:700; padding:2px 8px;
            border-bottom:1px solid var(--border); }
.app-row .q-label, .app-row > div { overflow:hidden; text-overflow:ellipsis; }
.pane-run { flex:1.3; }
.run-top { padding:8px; border-bottom:1px solid var(--border); }
.run-title { font-weight:700; font-size:1.05rem; }
.run-sub { color:var(--muted); margin-bottom:8px; }
.arg-controls { display:flex; flex-direction:column; gap:6px; margin:8px 0; }
.arg-row { display:flex; align-items:center; gap:10px; }
.arg-label { width:120px; color:var(--fg); }
.arg-input { flex:1; max-width:420px; }
.run-buttons { display:flex; gap:10px; margin-top:10px; }
.run-log { flex:1; min-height:0; margin:6px; padding:6px; border-radius:4px;
           background:var(--log-bg); color:var(--log-fg); white-space:pre-wrap; }
"""


def build() -> None:
    ui.add_css(CSS)
    # Prevent Tab / arrow keys from scrolling the page or moving native focus while
    # navigating panes; typing in a field is left untouched.
    ui.add_head_html(
        "<script>document.addEventListener('keydown',function(e){"
        "var t=(e.target.tagName||'').toLowerCase();"
        "if(t==='input'||t==='textarea')return;"
        "if(e.key==='Tab'||e.key==='ArrowUp'||e.key==='ArrowDown')e.preventDefault();"
        "},true);</script>"
    )
    refs["dark"] = ui.dark_mode(state.get("dark", True))
    ui.keyboard(on_key=_on_key)

    ui.query("body").classes("m-0")
    ui.query(".nicegui-content").classes("w-full h-screen p-0 gap-0 flex-nowrap")

    _init()  # populate state before the panes render for the first time

    with ui.column().classes("w-full h-screen p-0 gap-0"):
        # Top bar.
        with ui.element("div").classes("bar w-full"):
            ui.label("stello · control panel").classes("bar-title")
            refs["subtitle"] = ui.label().classes("bar-sub")
            ui.element("div").classes("bar-spacer")
            refs["theme_btn"] = ui.button(_theme_label(), on_click=_toggle_theme).props("flat dense")

        # Three panes.
        with ui.row().classes("w-full flex-1 min-h-0 no-wrap gap-0"):
            with ui.column().classes("h-full min-h-0 gap-0").style("width:24%"):
                projects_panel()
            with ui.column().classes("h-full min-h-0 gap-0").style("flex:1"):
                apps_panel()
            with ui.column().classes("h-full min-h-0 gap-0").style("width:38%"):
                run_panel()

        # Footer hints.
        with ui.element("div").classes("footer w-full"):
            ui.label("↑↓ navigate   ·   Tab / Shift+Tab switch pane   ·   Enter open   ·   click to open")

    _refresh_bar()
    ui.timer(0.6, _tick)


def _refresh_bar() -> None:
    label = refs.get("subtitle")
    if label is None:
        return
    project = state["project"]
    label.text = "no project" if not project else f"{project} · {len(state['apps'])} app(s)"


def _theme_label() -> str:
    return "☀ light" if state.get("dark", True) else "☾ dark"


def _toggle_theme() -> None:
    dark = refs["dark"]
    dark.toggle()
    state["dark"] = dark.value
    if (btn := refs.get("theme_btn")) is not None:
        btn.text = _theme_label()


def _init() -> None:
    """Load state for the active project (or the first) before the panes render."""
    infos = core.list_projects()
    if not infos:
        _load_project(None)
        return
    active = core.active_project()
    idx = next((i for i, info in enumerate(infos) if info.name == active), 0)
    state["proj_sel"] = idx
    _load_project(infos[idx].name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello dashboard (web control panel).")
    parser.add_argument("--port", type=int, default=8080, help="port to serve on")
    parser.add_argument("--theme", default="dark", help="dark or light")
    args = parser.parse_args()
    state["dark"] = args.theme.lower() != "light"
    build()
    ui.run(
        port=args.port,
        title="stello dashboard",
        reload=False,
        show=not os.environ.get("STELLO_CP_NO_SHOW"),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
