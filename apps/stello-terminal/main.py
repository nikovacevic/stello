"""Stello TUI — a Textual control panel for your stello projects.

This app *is* a stello application, and it doubles as a control panel for all of them.
It reuses stello's own library to:

- browse the initialized projects under ``~/.stello/projects`` (left pane),
- list and launch the applications in whichever project you're browsing (middle pane),
- and set the active project (press ``o`` — the same effect as ``stello open``).

Browsing is non-destructive: arrowing through projects only previews them. Only ``o``
changes the active project in ``config.yaml``. The Run button launches the selected app
as a supervised child (via ``core.launch_supervised``) and streams its output into the log
panel, composing its args from the on-screen controls.

It receives its own declared args (``--theme``, ``--compact``) from stello, which is how
stello hands declared args to any application.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, Static

from stello import core
from stello.models import Application, ArgType

SELF_SCRIPT = Path(__file__).resolve()


def _args_summary(app: Application) -> str:
    if not app.args:
        return "(no args)"
    return ", ".join(f"{a.name}:{a.type.value}={a.default}" for a in app.args)


class StelloTUI(App):
    """A control panel for the stello projects on this machine."""

    CSS = """
    #projects-pane { width: 26%; border-right: solid $panel; }
    #apps-pane { width: 34%; border-right: solid $panel; }
    #right { width: 40%; padding: 0 1; }
    .pane-title { text-style: bold; padding: 0 1; color: $text-muted; }
    #projects, #apps { height: 1fr; }
    #detail { padding: 1 0; color: $text-muted; }
    #arg-controls { height: auto; max-height: 40%; }
    .arg-row { height: 3; }
    .arg-row Label { width: 16; content-align: left middle; height: 3; }
    #run-buttons { height: auto; margin: 1 0; }
    #run-buttons Button { margin-right: 2; }
    #output { height: 1fr; border: round $panel; }
    """

    BINDINGS = [
        ("o", "open_project", "Open project"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, theme_name: str = "dark", compact: bool = False) -> None:
        super().__init__()
        self.theme_name = theme_name
        self.compact = compact
        self.project_names: list[str] = [p.name for p in core.list_projects()]
        self.current_project: str | None = None
        self.current_project_path: Path | None = None
        self.apps: list[Application] = []
        self.selected: Application | None = None
        self.load_error: str | None = None
        # Supervised launches whose output we stream into the #output log.
        self._supervised: list[core.LaunchedProcess] = []
        self._pushed: dict[int, int] = {}
        self._exited: set[int] = set()
        # Most recent launch per app name, so Stop can target the selected app's process.
        self._procs: dict[str, core.LaunchedProcess] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="projects-pane"):
                yield Label("Projects  (o: open)", classes="pane-title")
                yield DataTable(id="projects", cursor_type="row")
            with Vertical(id="apps-pane"):
                yield Label("Applications", classes="pane-title")
                yield DataTable(id="apps", cursor_type="row")
            with Vertical(id="right"):
                yield Static(id="detail")
                yield VerticalScroll(id="arg-controls")
                with Horizontal(id="run-buttons"):
                    yield Button("▶ Run", id="run", variant="success")
                    yield Button("■ Stop", id="stop", variant="error", disabled=True)
                yield Log(id="output")
        yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()
        self.title = "stello · control panel"

        self.query_one("#projects", DataTable).add_columns("project")
        apps_table = self.query_one("#apps", DataTable)
        if self.compact:
            apps_table.add_columns("app", "args")
        else:
            apps_table.add_columns("app", "dir", "script", "args")

        if not self.project_names:
            self.sub_title = "no initialized projects"
            self.query_one("#detail", Static).update(
                "No projects initialized. Run `stello init <project_name> <remote_git_url>`."
            )
            return

        self._populate_projects()
        # Start on the active project if there is one, else the first.
        active = core.active_project()
        initial = active if active in self.project_names else self.project_names[0]
        self._load_project(initial)
        self._move_cursor("#projects", self.project_names.index(initial))
        self.set_interval(0.5, self._stream_logs)

    # --- data loading -----------------------------------------------------

    def _load_project(self, name: str) -> None:
        self.current_project = name
        try:
            self.current_project_path = core.project_path(name)
            self.apps = core.apps_for(name)
            self.load_error = None
        except Exception as exc:  # surface manifest problems, don't crash
            self.apps = []
            self.load_error = str(exc)

        self.sub_title = (
            f"{name} · {self.load_error}"
            if self.load_error
            else f"{name} · {len(self.apps)} app(s)"
        )
        self._populate_apps()

        if self.apps:
            self._render_controls(self.apps[0])
            self._move_cursor("#apps", 0)
        else:
            self.selected = None
            self.query_one("#arg-controls", VerticalScroll).remove_children()
            self.query_one("#detail", Static).update(
                self.load_error or "No applications defined in this project's stello.yaml."
            )

    def _populate_projects(self) -> None:
        table = self.query_one("#projects", DataTable)
        table.clear()
        active = core.active_project()
        for name in self.project_names:
            marker = "*" if name == active else " "
            table.add_row(f"{marker} {name}", key=name)

    def _populate_apps(self) -> None:
        table = self.query_one("#apps", DataTable)
        table.clear()
        for app in self.apps:
            if self.compact:
                table.add_row(app.name, _args_summary(app), key=app.name)
            else:
                table.add_row(app.name, app.dir, app.script, _args_summary(app), key=app.name)

    def _render_controls(self, app: Application) -> None:
        self.selected = app
        self.query_one("#detail", Static).update(f"[b]{app.name}[/b]\n{app.dir} → {app.script}")
        controls = self.query_one("#arg-controls", VerticalScroll)
        controls.remove_children()
        rows = []
        for arg in app.args:
            if arg.type is ArgType.BOOL:
                widget = Checkbox(value=bool(arg.default), id=f"arg-{arg.name}")
            else:
                widget = Input(value=str(arg.default), id=f"arg-{arg.name}")
            rows.append(Horizontal(Label(arg.name), widget, classes="arg-row"))
        controls.mount(*rows)
        self._refresh_run_buttons()

    def _refresh_run_buttons(self) -> None:
        """Enable Run/Stop to match whether the selected app has a running process."""
        running = False
        if self.selected is not None:
            proc = self._procs.get(self.selected.name)
            running = bool(proc and proc.is_running())
        try:
            self.query_one("#run", Button).disabled = running
            self.query_one("#stop", Button).disabled = not running
        except Exception:
            pass

    # --- helpers ----------------------------------------------------------

    def _move_cursor(self, table_id: str, row: int) -> None:
        try:
            self.query_one(table_id, DataTable).move_cursor(row=row)
        except Exception:
            pass

    def _app_by_name(self, name: str) -> Application | None:
        return next((a for a in self.apps if a.name == name), None)

    def _notify(self, message: str) -> None:
        try:
            self.notify(message)
        except Exception:
            self.query_one("#output", Log).write_line(f"· {message}")

    def _apply_theme(self) -> None:
        # Textual's theme API has shifted across versions; be defensive.
        want_dark = self.theme_name.lower() != "light"
        try:
            if hasattr(type(self), "theme"):
                self.theme = "textual-dark" if want_dark else "textual-light"
            else:
                self.dark = want_dark
        except Exception:
            pass

    # --- events / actions -------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        name = event.row_key.value
        if name is None:
            return
        if event.data_table.id == "projects":
            if name != self.current_project:
                self._load_project(name)
        elif event.data_table.id == "apps":
            app = self._app_by_name(name)
            if app is not None and (self.selected is None or app.name != self.selected.name):
                self._render_controls(app)

    def action_open_project(self) -> None:
        if not self.current_project:
            return
        core.set_active(self.current_project)
        self._populate_projects()  # refresh the `*` marker
        self._move_cursor("#projects", self.project_names.index(self.current_project))
        self._notify(f"Opened '{self.current_project}' — now the active project")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._run_selected()
        elif event.button.id == "stop":
            self._stop_selected()

    def _run_selected(self) -> None:
        if self.selected is None or self.current_project is None:
            return
        app = self.selected
        output = self.query_one("#output", Log)
        overrides = self._collect_overrides(app)
        try:
            cmd = core.command_for(self.current_project, app.name, overrides)
        except Exception as exc:
            output.write_line(f"! {exc}")
            return
        output.write_line(f"$ {' '.join(shlex.quote(part) for part in cmd)}")

        if self.current_project_path and app.resolved_script(self.current_project_path) == SELF_SCRIPT:
            output.write_line("  (skipped) refusing to launch the TUI from itself")
            return
        try:
            proc = core.launch_supervised(self.current_project, app.name, overrides)
        except Exception as exc:
            output.write_line(f"  ! failed to launch: {exc}")
            return
        self._supervised.append(proc)
        self._procs[app.name] = proc
        output.write_line(f"  launched {app.name} (pid {proc.pid}) — streaming output:")
        self._refresh_run_buttons()

    def _stop_selected(self) -> None:
        if self.selected is None:
            return
        proc = self._procs.get(self.selected.name)
        if proc is None or not proc.is_running():
            return
        proc.stop()
        self.query_one("#output", Log).write_line(f"[{proc.label}] stopping (pid {proc.pid}) …")
        self._refresh_run_buttons()

    def _stream_logs(self) -> None:
        """Poll supervised processes and push new output/exit lines into the log."""
        output = self.query_one("#output", Log)
        for proc in self._supervised:
            lines = proc.lines()
            seen = self._pushed.get(id(proc), 0)
            if len(lines) > seen:
                for line in lines[seen:]:
                    output.write_line(f"[{proc.label}] {line}")
                self._pushed[id(proc)] = len(lines)
            if not proc.is_running() and id(proc) not in self._exited:
                self._exited.add(id(proc))
                output.write_line(f"[{proc.label}] (exited {proc.returncode})")
                self._refresh_run_buttons()

    def _collect_overrides(self, app: Application) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for arg in app.args:
            widget = self.query_one(f"#arg-{arg.name}")
            if isinstance(widget, Checkbox):
                overrides[arg.name] = "true" if widget.value else "false"
            else:
                overrides[arg.name] = widget.value
        return overrides


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello project control panel.")
    parser.add_argument("--theme", default="dark", help="dark or light")
    parser.add_argument("--compact", action="store_true", help="denser tables")
    args = parser.parse_args()
    StelloTUI(theme_name=args.theme, compact=args.compact).run()


if __name__ == "__main__":
    main()
