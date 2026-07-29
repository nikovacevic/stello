"""Stello TUI — a Textual control panel for your stello projects.

This app *is* a stello application, and it doubles as a control panel for all of them.
It reuses stello's own library to:

- browse the initialized projects under ``~/.stello/projects`` (left pane),
- list and launch the applications in whichever project you're browsing (middle pane),
- and set the active project (press ``o`` — the same effect as ``stello open``).

Browsing is non-destructive: arrowing through projects only previews them. Only ``o``
changes the active project in ``config.yaml``. The Run button starts the selected app via
``uv run`` (detached), composing its args from the on-screen controls.

It receives its own declared args (``--theme``, ``--compact``) from stello, which is how
stello hands declared args to any application.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, Static

from stello import config, projects
from stello.manifest import load_manifest
from stello.models import Application, ArgType
from stello.run import resolve_args

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
    #run { margin: 1 0; }
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
        self.project_names: list[str] = projects.list_projects()
        self.current_project: str | None = None
        self.current_project_path: Path | None = None
        self.apps: list[Application] = []
        self.selected: Application | None = None
        self.load_error: str | None = None

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
                yield Button("▶ Run", id="run", variant="success")
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
        active = config.active_project()
        initial = active if active in self.project_names else self.project_names[0]
        self._load_project(initial)
        self._move_cursor("#projects", self.project_names.index(initial))

    # --- data loading -----------------------------------------------------

    def _load_project(self, name: str) -> None:
        self.current_project = name
        self.current_project_path = projects.project_path(name)
        try:
            self.apps = load_manifest(self.current_project_path).applications
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
        active = config.active_project()
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
        config.set_active_project(self.current_project)
        self._populate_projects()  # refresh the `*` marker
        self._move_cursor("#projects", self.project_names.index(self.current_project))
        self._notify(f"Opened '{self.current_project}' — now the active project")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "run" or self.selected is None or self.current_project_path is None:
            return
        app = self.selected
        output = self.query_one("#output", Log)
        try:
            argv = resolve_args(app, self._collect_overrides(app))
        except Exception as exc:
            output.write_line(f"! {exc}")
            return
        cmd = ["uv", "run", "--directory", str(app.resolved_dir(self.current_project_path)), app.script, *argv]
        output.write_line(f"$ {' '.join(shlex.quote(part) for part in cmd)}")

        if app.resolved_script(self.current_project_path) == SELF_SCRIPT:
            output.write_line("  (skipped) refusing to launch the TUI from itself")
            return
        try:
            # Detached so the child (e.g. a web server) outlives this event and
            # doesn't fight the TUI for the terminal.
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            output.write_line(f"  ! failed to launch: {exc}")
            return
        output.write_line(f"  launched {app.name} in {self.current_project} (pid {proc.pid})")

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
