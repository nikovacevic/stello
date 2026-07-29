"""Stello Dashboard — a NiceGUI web control panel for all your stello projects.

One of stello's own applications: the ``dashboard`` app in the repo's ``stello.yaml``, run
like any other project's app with ``stello run stello/dashboard``. A browser-based
counterpart to the ``terminal`` TUI, and like it a thin view over ``stello.core`` (which it
lists as a dependency).

The design takes its cues from GitHub (Primer): a system sans-serif UI, a light and a dark
theme, bordered cards, and restrained spacing — deliberately *not* a terminal. Layout:

- a header with the ``stello`` wordmark (and version) on the left and a light/dark theme
  selector on the right;
- a left **Projects** pane: the initialized projects, with a ``+`` to install a new one;
  clicking a project (or arrowing to it) selects it and drives the other panes;
- a top **Project** pane for the selection: name, current ref, and description, with an
  **Update** button whose dropdown optionally picks a ref (plain Update keeps the current);
- an **Apps** pane listing the selected project's applications;
- an **Application** pane: ``<project>/<app>`` title, description, **Run**/**Stop** controls,
  and two tabs — **Args** (configure arguments) and **Logs** (watch output stream). Run
  switches to Logs automatically; Stop leaves the tab as-is.

Navigate panes with Tab / Shift+Tab; move within a list with the arrow keys. The slow git
operations (install, update, list refs) run off the event loop via ``run.io_bound`` so the
UI stays responsive.

Set STELLO_CP_NO_SHOW=1 to not auto-open a browser (used by tests).
"""

from __future__ import annotations

import argparse
import os
from functools import partial
from pathlib import Path

from nicegui import run as ng_run, ui

from stello import __version__, core
from stello.models import Application, ArgType

SELF_SCRIPT = Path(__file__).resolve()

# The focusable panes, in Tab order.
PANES = ("projects", "apps", "application")

# Shared, single-user state (this panel, like the TUI, drives one machine).
state: dict = {
    "dark": True,
    "focus": "projects",       # active pane: one of PANES
    "proj_sel": 0,             # highlighted row in Projects
    "app_sel": 0,              # highlighted row in Apps
    "project": None,           # selected project name
    "project_ref": None,       # its current ref
    "project_desc": None,      # its description
    "apps": [],                # its Applications
    "load_error": None,        # manifest error, if any
    "app": None,               # Application shown in the Application pane
    "app_tab": "args",         # 'args' or 'logs'
    "arg_values": {},          # arg name -> current value (persists across tab switches)
    "proc": None,              # LaunchedProcess for the shown app, if started
    "proc_alive": None,        # last-seen running state, to refresh on change
    "log_pushed": 0,           # lines already pushed to the live log
}
procs: dict[str, core.LaunchedProcess] = {}   # label -> most recent launch
refs: dict = {}                               # persistent widget handles (log, dark, ref_menu)


def _label_for(project: str, app: Application) -> str:
    return f"{project}/{app.name}"


def _would_relaunch_dashboard(project: str, app: Application) -> bool:
    """True if launching ``app`` would start another instance of this dashboard."""
    try:
        return app.resolved_script(core.project_path(project)) == SELF_SCRIPT
    except Exception:  # noqa: BLE001 - if we can't tell, fall through and let it try
        return False


def _default_value(arg) -> object:
    return bool(arg.default) if arg.type is ArgType.BOOL else str(arg.default)


# --- selection / loading --------------------------------------------------

def _load_project(name: str | None) -> None:
    """Populate state for a project (no widget refresh — safe before the loop)."""
    state["project"] = name
    state["app_sel"] = 0
    if name is None:
        state.update(apps=[], load_error=None, project_ref=None, project_desc=None, app=None)
        return
    try:
        state["project_ref"] = core.current_ref(name)
    except Exception:  # noqa: BLE001
        state["project_ref"] = None
    try:
        ref, manifest = core.describe_project(name)
        state["project_ref"] = ref
        state["project_desc"] = manifest.description
        state["apps"] = list(manifest.applications)
        state["load_error"] = None
    except Exception as exc:  # noqa: BLE001 - surface manifest problems, don't crash
        state["project_desc"] = None
        state["apps"] = []
        state["load_error"] = str(exc)


def _set_app(app: Application | None, idx: int) -> None:
    """Load an application into state (no refresh)."""
    state["app_sel"] = idx
    state["app"] = app
    state["app_tab"] = "args"
    if app is None:
        state["arg_values"] = {}
        state["proc"] = None
        state["proc_alive"] = None
        return
    state["arg_values"] = {a.name: _default_value(a) for a in app.args}
    proc = procs.get(_label_for(state["project"], app))
    state["proc"] = proc
    state["proc_alive"] = proc.is_running() if proc else None


def _select_project(name: str, idx: int) -> None:
    state["focus"] = "projects"
    state["proj_sel"] = idx
    _load_project(name)
    apps = state["apps"]
    _set_app(apps[0] if apps else None, 0)
    projects_panel.refresh()
    project_panel.refresh()
    apps_panel.refresh()
    application_panel.refresh()


def _select_app(app: Application, idx: int) -> None:
    state["focus"] = "apps"
    _set_app(app, idx)
    apps_panel.refresh()
    application_panel.refresh()


def _reload_current_project() -> None:
    """Re-read the current project after an update, keeping the same app selected if we can."""
    name = state["project"]
    if name is None:
        return
    current_app = state["app"].name if state["app"] else None
    _load_project(name)
    apps = state["apps"]
    idx = next((i for i, a in enumerate(apps) if a.name == current_app), 0)
    _set_app(apps[idx] if apps else None, idx)
    project_panel.refresh()
    apps_panel.refresh()
    application_panel.refresh()


# --- run: start / stop / stream ------------------------------------------

def _collect_overrides(app: Application) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for arg in app.args:
        value = state["arg_values"].get(arg.name, arg.default)
        overrides[arg.name] = (
            ("true" if value else "false") if arg.type is ArgType.BOOL else str(value)
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
    if _would_relaunch_dashboard(project, app):
        ui.notify("Refusing to launch the dashboard from itself", type="warning")
        return
    try:
        proc = core.launch_supervised(project, app.name, _collect_overrides(app))
    except Exception as exc:  # noqa: BLE001
        ui.notify(str(exc), type="negative")
        return
    procs[label] = proc
    state["proc"] = proc
    state["proc_alive"] = True
    state["log_pushed"] = 0
    state["app_tab"] = "logs"  # Run switches to Logs.
    ui.notify(f"Started {app.name} (pid {proc.pid})", type="positive")
    application_panel.refresh()


def _stop() -> None:
    proc = state["proc"]
    if proc is None or not proc.is_running():
        return
    proc.stop()
    ui.notify(f"Stopping {proc.label}")
    application_panel.refresh()  # keeps the current tab (Stop doesn't switch)


def _tick() -> None:
    """Poll the shown process: stream new output and flip buttons on state change."""
    proc = state["proc"]
    if proc is None:
        return
    log = refs.get("log")
    if state["app_tab"] == "logs" and log is not None:
        lines = proc.lines()
        seen = state["log_pushed"]
        if len(lines) > seen:
            for line in lines[seen:]:
                log.push(line)
            state["log_pushed"] = len(lines)
    alive = proc.is_running()
    if state["proc_alive"] != alive:
        state["proc_alive"] = alive
        application_panel.refresh()


# --- install / update -----------------------------------------------------

def _open_install_dialog() -> None:
    with ui.dialog() as dialog, ui.element("div").classes("dialog-card"):
        ui.label("Install a project").classes("dialog-title")
        name = ui.input("Project name").props("outlined dense").classes("dialog-input")
        url = ui.input("Git remote URL").props("outlined dense").classes("dialog-input")
        ref = ui.input("Ref (optional)").props("outlined dense").classes("dialog-input")
        with ui.element("div").classes("dialog-actions"):
            _btn("Cancel", dialog.close, kind="default")
            _btn("Install", partial(_do_install, dialog, name, url, ref), kind="run")
    dialog.open()


async def _do_install(dialog, name_in, url_in, ref_in) -> None:
    name = (name_in.value or "").strip()
    url = (url_in.value or "").strip()
    ref = (ref_in.value or "").strip() or None
    if not name or not url:
        ui.notify("Name and git remote URL are required.", type="warning")
        return
    dialog.close()
    ui.notify(f"Installing {name}…")
    try:
        await ng_run.io_bound(core.add_project, name, url, ref)
    except Exception as exc:  # noqa: BLE001
        ui.notify(f"Install failed: {exc}", type="negative")
        return
    ui.notify(f"Installed {name}", type="positive")
    infos = core.list_projects()
    idx = next((i for i, inf in enumerate(infos) if inf.name == name), 0)
    if infos:
        _select_project(infos[idx].name, idx)


async def _update_current() -> None:
    name = state["project"]
    if not name:
        return
    ui.notify(f"Updating {name}…")
    try:
        await ng_run.io_bound(core.update_project, name, None)
    except Exception as exc:  # noqa: BLE001
        ui.notify(f"Update failed: {exc}", type="negative")
        return
    _reload_current_project()
    ui.notify(f"Updated {name} ({state.get('project_ref')})", type="positive")


async def _update_to(ref: str, *_) -> None:
    name = state["project"]
    if not name:
        return
    ui.notify(f"Switching {name} to {ref}…")
    try:
        await ng_run.io_bound(core.update_project, name, ref)
    except Exception as exc:  # noqa: BLE001
        ui.notify(f"Update failed: {exc}", type="negative")
        return
    _reload_current_project()
    ui.notify(f"Updated {name} ({state.get('project_ref')})", type="positive")


async def _populate_ref_menu() -> None:
    """Fill the Update dropdown when it opens (ls-remote runs off the event loop)."""
    name = state["project"]
    menu = refs.get("ref_menu")
    if not name or menu is None:
        return
    try:
        listing = await ng_run.io_bound(core.list_refs, name)
    except Exception as exc:  # noqa: BLE001
        menu.clear()
        with menu:
            ui.menu_item(f"! {exc}").props("disable")
        return
    menu.clear()
    with menu:
        if listing.branches:
            ui.menu_item("Branches").props("disable").classes("menu-head")
            for b in listing.branches:
                _ref_menu_item(b, listing.current)
        if listing.tags:
            ui.menu_item("Tags").props("disable").classes("menu-head")
            for t in listing.tags:
                _ref_menu_item(t, listing.current)
        if not listing.branches and not listing.tags:
            ui.menu_item("(no refs)").props("disable")


def _ref_menu_item(ref: str, current: str) -> None:
    label = f"{ref}  ●" if ref == current else ref
    ui.menu_item(label, on_click=partial(_update_to, ref))


# --- keyboard navigation --------------------------------------------------

def _set_focus(pane: str) -> None:
    state["focus"] = pane
    projects_panel.refresh()
    apps_panel.refresh()
    application_panel.refresh()


def _cycle_focus(delta: int) -> None:
    idx = (PANES.index(state["focus"]) + delta) % len(PANES)
    _set_focus(PANES[idx])


def _move(delta: int) -> None:
    focus = state["focus"]
    if focus == "projects":
        infos = core.list_projects()
        if not infos:
            return
        i = max(0, min(len(infos) - 1, state["proj_sel"] + delta))
        _select_project(infos[i].name, i)
    elif focus == "apps":
        apps = state["apps"]
        if not apps:
            return
        i = max(0, min(len(apps) - 1, state["app_sel"] + delta))
        _select_app(apps[i], i)


def _drill() -> None:
    focus = state["focus"]
    if focus == "projects":
        _set_focus("apps")
    elif focus == "apps":
        _set_focus("application")


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
        _drill()


# --- buttons --------------------------------------------------------------

# Button colors as inline styles: inline wins over Quasar's own classes everywhere,
# including inside teleported dialogs where class-based overrides don't take.
_BTN_STYLE = {
    "default": "background:var(--btn) !important;color:var(--fg) !important;border:1px solid var(--btn-border) !important;",
    "primary": "background:var(--accent) !important;color:#fff !important;",
    "run": "background:var(--success) !important;color:#fff !important;",
    "stop": "background:var(--danger) !important;color:#fff !important;",
}


def _btn(label: str, on_click, *, kind: str = "default", disabled: bool = False, icon: str | None = None):
    b = ui.button(label, on_click=on_click, icon=icon).props("no-caps unelevated dense")
    b.classes(f"gh-btn gh-{kind}")
    b.style(_BTN_STYLE.get(kind, _BTN_STYLE["default"]))
    if disabled:
        b.props("disable")
    return b


# --- panes ----------------------------------------------------------------

@ui.refreshable
def projects_panel() -> None:
    focused = state["focus"] == "projects"
    with ui.element("div").classes("card projects" + (" focus" if focused else "")):
        with ui.element("div").classes("card-head"):
            ui.label("Projects").classes("card-title")
            ui.element("div").classes("spacer")
            ui.button(icon="add", on_click=_open_install_dialog).props(
                "no-caps unelevated dense"
            ).classes("gh-btn gh-primary addbtn").style(_BTN_STYLE["primary"]).tooltip("Install a project")
        with ui.element("div").classes("card-body"):
            infos = core.list_projects()
            if not infos:
                ui.label("No projects yet. Click + to install one.").classes("empty")
                return
            state["proj_sel"] = max(0, min(len(infos) - 1, state["proj_sel"]))
            for i, info in enumerate(infos):
                sel = i == state["proj_sel"]
                row = ui.element("div").classes("list-row" + (" sel" if sel else ""))
                row.on("click", partial(_select_project, info.name, i))
                with row:
                    ui.label(info.name)
                    if sel:
                        ui.icon("chevron_right").classes("chev")


@ui.refreshable
def project_panel() -> None:
    with ui.element("div").classes("card project-card"):
        name = state["project"]
        if name is None:
            with ui.element("div").classes("proj-detail"):
                ui.label("Select or install a project.").classes("empty")
            return
        with ui.element("div").classes("proj-detail"):
            with ui.element("div").classes("proj-head"):
                ui.label(name).classes("proj-name")
                ui.element("div").classes("spacer")
                with ui.element("div").classes("update-group"):
                    _btn("Update", _update_current, kind="primary")
                    caret = ui.button(icon="expand_more").props(
                        "no-caps unelevated dense"
                    ).classes("gh-btn gh-primary caret").style(_BTN_STYLE["primary"])
                    with caret:
                        ref_menu = ui.menu().props('anchor="bottom right" self="top right"')
                        with ref_menu:
                            ui.menu_item("Loading…").props("disable")
                    refs["ref_menu"] = ref_menu
                    ref_menu.on("show", _populate_ref_menu)
            ref = state.get("project_ref")
            if ref:
                ui.label(f"[{ref}]").classes("ref-chip")
            desc = state.get("project_desc")
            ui.label(desc if desc else "No description.").classes("proj-desc")


@ui.refreshable
def apps_panel() -> None:
    focused = state["focus"] == "apps"
    with ui.element("div").classes("card apps" + (" focus" if focused else "")):
        with ui.element("div").classes("card-head"):
            ui.label("Apps").classes("card-title")
        with ui.element("div").classes("card-body"):
            if state["project"] is None:
                ui.label("Select a project.").classes("empty")
                return
            if state["load_error"]:
                ui.label(state["load_error"]).classes("error")
                return
            apps = state["apps"]
            if not apps:
                ui.label("No apps in this project's stello.yaml.").classes("empty")
                return
            state["app_sel"] = max(0, min(len(apps) - 1, state["app_sel"]))
            for i, app in enumerate(apps):
                sel = i == state["app_sel"]
                row = ui.element("div").classes("list-row" + (" sel" if sel else ""))
                row.on("click", partial(_select_app, app, i))
                with row:
                    ui.label(app.name)
                    if sel:
                        ui.icon("chevron_right").classes("chev")


@ui.refreshable
def application_panel() -> None:
    focused = state["focus"] == "application"
    with ui.element("div").classes("card application" + (" focus" if focused else "")):
        app = state["app"]
        project = state["project"]
        with ui.element("div").classes("card-head"):
            ui.label(f"{project}/{app.name}" if app else "Application").classes("card-title")
            ui.element("div").classes("spacer")
            if app is not None:
                running = bool(state["proc"] and state["proc"].is_running())
                _btn("Run", _start, kind="run", disabled=running, icon="play_arrow")
                _btn("Stop", _stop, kind="stop", disabled=not running, icon="stop")
        if app is None:
            with ui.element("div").classes("card-body"):
                ui.label("Select an application to run.").classes("empty")
            return
        if app.description:
            ui.label(app.description).classes("app-desc")
        # Tabs.
        with ui.element("div").classes("tabbar"):
            for key, label in (("args", "Args"), ("logs", "Logs")):
                tab = ui.element("div").classes("tab" + (" tab-active" if state["app_tab"] == key else ""))
                tab.on("click", partial(_set_tab, key))
                with tab:
                    ui.label(label)
        # Body: Args or Logs.
        if state["app_tab"] == "args":
            with ui.element("div").classes("card-body args-body"):
                if not app.args:
                    ui.label("This application has no arguments.").classes("empty")
                for arg in app.args:
                    with ui.element("div").classes("arg-row"):
                        with ui.element("div").classes("arg-name-col"):
                            ui.label(arg.name).classes("arg-name")
                            if arg.description:
                                ui.label(arg.description).classes("arg-desc")
                        _arg_input(arg)
        else:
            log = ui.log(max_lines=1000).classes("log")
            refs["log"] = log
            proc = state["proc"]
            lines = proc.lines() if proc else []
            for line in lines:
                log.push(line)
            state["log_pushed"] = len(lines)
            if proc is not None and not proc.is_running():
                log.push(f"(exited {proc.returncode})")


def _arg_input(arg) -> None:
    value = state["arg_values"].get(arg.name, _default_value(arg))
    if arg.type is ArgType.BOOL:
        ui.checkbox(value=bool(value), on_change=partial(_arg_change, arg.name))
    else:
        ui.input(value=str(value), on_change=partial(_arg_change, arg.name)).props(
            "outlined dense"
        ).classes("arg-input")


def _arg_change(name: str, e) -> None:
    state["arg_values"][name] = e.value


def _set_tab(key: str, *_) -> None:
    state["app_tab"] = key
    application_panel.refresh()


# --- theme / layout -------------------------------------------------------

CSS = """
:root {
  --canvas:#f6f8fa; --card:#ffffff; --border:#d1d9e0;
  --fg:#1f2328; --muted:#59636e; --accent:#0969da; --accent-subtle:#ddf4ff;
  --success:#1f883d; --success-hover:#1a7f37; --danger:#cf222e; --danger-hover:#a40e26;
  --btn:#f6f8fa; --btn-hover:#eef1f4; --btn-border:#d1d9e0;
  --log-bg:#0d1117; --log-fg:#e6edf3;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
body.body--dark {
  --canvas:#0d1117; --card:#151b23; --border:#3d444d;
  --fg:#e6edf3; --muted:#9198a1; --accent:#4493f8; --accent-subtle:rgba(56,139,253,0.15);
  --success:#238636; --success-hover:#2ea043; --danger:#da3633; --danger-hover:#f85149;
  --btn:#21262d; --btn-hover:#30363d; --btn-border:#3d444d;
  --log-bg:#010409; --log-fg:#e6edf3;
}
* { font-family: var(--font); }
.material-icons, .material-icons-outlined, .q-icon { font-family:'Material Icons' !important; }
body { background:var(--canvas); color:var(--fg); }

.header { display:flex; align-items:center; padding:10px 16px; gap:10px;
          border-bottom:1px solid var(--border); background:var(--card); }
.brand { display:flex; align-items:baseline; gap:8px; }
.brand-name { font-size:1.15rem; font-weight:600; letter-spacing:.2px; }
.brand-ver { font-size:.8rem; color:var(--muted); }
.spacer { flex:1; }

.content { display:flex; flex:1; min-height:0; gap:12px; padding:12px; }
.right { display:flex; flex-direction:column; flex:1; min-width:0; min-height:0; gap:12px; }
.lower { display:flex; flex:1; min-height:0; gap:12px; }

.card { background:var(--card); border:1px solid var(--border); border-radius:8px;
        display:flex; flex-direction:column; min-height:0; min-width:0; overflow:hidden; }
.card.focus { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
.projects { flex:0 0 240px; }
.project-card { flex:0 0 auto; }
.apps { flex:0 0 240px; }
.application { flex:1; }

.card-head { display:flex; align-items:center; gap:8px; padding:10px 12px;
             border-bottom:1px solid var(--border); }
.card-title { font-weight:600; font-size:.95rem; }
.card-body { flex:1; min-height:0; overflow:auto; padding:6px; }
.empty { color:var(--muted); padding:10px; }
.error { color:var(--danger); padding:10px; white-space:pre-wrap; }

.list-row { display:flex; align-items:center; justify-content:space-between;
            padding:6px 10px; border-radius:6px; cursor:pointer; color:var(--fg); }
.list-row:hover { background:var(--btn-hover); }
.list-row.sel { background:var(--accent-subtle); font-weight:600; }
.card.focus .list-row.sel { box-shadow:inset 0 0 0 1px var(--accent); }
.list-row .chev { color:var(--muted); font-size:1.1rem; }

/* project detail */
.proj-detail { padding:12px 14px; }
.proj-head { display:flex; align-items:flex-start; }
.proj-name { font-size:1.15rem; font-weight:600; }
.ref-chip { display:inline-block; font-family:var(--mono); font-size:.78rem; color:var(--muted);
            border:1px solid var(--border); border-radius:20px; padding:1px 10px; margin:8px 0 6px; }
.proj-desc { color:var(--muted); }

/* application */
.app-desc { color:var(--muted); padding:0 12px 4px; }
.tabbar { display:flex; gap:8px; padding:8px 12px 0; border-bottom:1px solid var(--border); }
.tab { padding:5px 12px; cursor:pointer; color:var(--muted); font-size:.85rem;
       border:1px solid transparent; border-radius:6px 6px 0 0; margin-bottom:-1px; }
.tab:hover { color:var(--fg); }
.tab-active { color:var(--fg); font-weight:600; border-color:var(--border);
              border-bottom-color:var(--card); background:var(--card); }
.args-body { padding:14px; }
.arg-row { display:flex; align-items:center; gap:16px; padding:6px 0; }
.arg-name-col { width:180px; flex:0 0 180px; }
.arg-name { font-family:var(--mono); font-size:.85rem; }
.arg-desc { color:var(--muted); font-size:.78rem; }
.arg-input { flex:1; max-width:460px; }
.log { flex:1; min-height:0; margin:0; padding:12px; background:var(--log-bg); color:var(--log-fg);
       font-family:var(--mono); font-size:.8rem; line-height:1.5; white-space:pre-wrap; }

/* buttons — GitHub look; colors are set inline (see _BTN_STYLE), shape/hover here */
.gh-btn.q-btn { border-radius:6px; font-weight:500; font-size:.82rem; text-transform:none;
                box-shadow:none; min-height:0; padding:4px 12px; }
.gh-default.q-btn:hover { background:var(--btn-hover) !important; }
.gh-run.q-btn:hover { background:var(--success-hover) !important; }
.gh-btn.q-btn.disabled, .gh-btn.q-btn[disabled] { opacity:.5; }
.addbtn.q-btn { padding:2px 6px; min-height:0; }
.update-group { display:flex; align-items:center; }
.update-group .gh-primary:first-child.q-btn { border-top-right-radius:0; border-bottom-right-radius:0; }
.update-group .caret.q-btn { border-top-left-radius:0; border-bottom-left-radius:0;
                             padding:4px 4px; border-left:1px solid rgba(255,255,255,.25); }
.menu-head { color:var(--muted); font-size:.72rem; font-weight:700; text-transform:uppercase;
             opacity:1 !important; letter-spacing:.4px; }
/* dropdown menu popup (rendered at body level) */
.q-menu { background:var(--card) !important; color:var(--fg) !important;
          border:1px solid var(--border); border-radius:8px;
          box-shadow:0 8px 24px rgba(0,0,0,.28) !important; }
.q-menu .q-item { min-height:32px; font-size:.85rem; color:var(--fg); }
.q-menu .q-item:hover { background:var(--btn-hover); }

/* theme toggle */
.theme-toggle.q-btn-group { box-shadow:none; border:1px solid var(--btn-border); border-radius:6px; }
.theme-toggle .q-btn { text-transform:none; font-size:.8rem; padding:3px 12px; min-height:0; }

/* dialog */
.dialog-card { background:var(--card); color:var(--fg); border:1px solid var(--border);
               border-radius:8px; padding:16px; min-width:380px; display:flex; flex-direction:column; gap:10px; }
.dialog-title { font-weight:600; font-size:1rem; margin-bottom:4px; }
.dialog-input { width:100%; }
.dialog-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:6px; }
"""


def build() -> None:
    ui.add_css(CSS)
    # Keep Tab / arrow keys from scrolling the page or moving native focus while navigating
    # panes; typing in a field is left untouched.
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

    _init()

    with ui.column().classes("w-full h-screen p-0 gap-0"):
        with ui.element("div").classes("header w-full"):
            with ui.element("div").classes("brand"):
                ui.label("stello").classes("brand-name")
                ui.label(f"v{__version__}").classes("brand-ver")
            ui.element("div").classes("spacer")
            ui.toggle(
                {"light": "Light", "dark": "Dark"},
                value="dark" if state["dark"] else "light",
                on_change=_on_theme,
            ).props("no-caps unelevated dense").classes("theme-toggle")

        with ui.element("div").classes("content w-full"):
            projects_panel()
            with ui.element("div").classes("right"):
                project_panel()
                with ui.element("div").classes("lower"):
                    apps_panel()
                    application_panel()

    ui.timer(0.6, _tick)


def _on_theme(e) -> None:
    dark = e.value == "dark"
    state["dark"] = dark
    dm = refs.get("dark")
    if dm is not None:
        dm.enable() if dark else dm.disable()


def _init() -> None:
    """Load state for the first project/app before the panes render."""
    infos = core.list_projects()
    if not infos:
        _load_project(None)
        return
    state["proj_sel"] = 0
    _load_project(infos[0].name)
    apps = state["apps"]
    _set_app(apps[0] if apps else None, 0)


@ui.page("/")
def _index() -> None:
    """Build the dashboard per client connection.

    Using an explicit page route (rather than NiceGUI's auto-index) is what lets this launch
    reliably as a stello application: the auto-index path rebuilds the page by re-running
    ``sys.argv[0]`` as ``__main__``; a page route builds it by calling this function instead.
    """
    build()


def run(port: int = 8080, theme: str = "dark") -> None:
    """Launch the NiceGUI dashboard."""
    state["dark"] = theme.lower() != "light"
    ui.run(
        port=port,
        title="stello dashboard",
        reload=False,
        show=not os.environ.get("STELLO_CP_NO_SHOW"),
    )


def main() -> None:
    """argparse entry point for running this module as a stello application."""
    parser = argparse.ArgumentParser(description="Stello dashboard (web control panel).")
    parser.add_argument("--port", type=int, default=8080, help="port to serve on")
    parser.add_argument("--theme", default="dark", help="dark or light")
    args = parser.parse_args()
    run(port=args.port, theme=args.theme)


if __name__ in {"__main__", "__mp_main__"}:
    main()
