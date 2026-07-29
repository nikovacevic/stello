"""Stello Dashboard — a Textual control panel for a stello project.

This app *is* a stello application: it lives in a stello project, and when run it
introspects that same project's ``stello.yaml`` (reusing stello's own parser), lists the
applications inside it, and offers dummy controls to "run" them. Nothing is actually
executed — the Run button just composes and shows the command stello would run.

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

from stello.manifest import load_manifest
from stello.models import Application, ArgType
from stello.run import resolve_args

# apps/dashboard/main.py -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]


def _args_summary(app: Application) -> str:
    if not app.args:
        return "(no args)"
    return ", ".join(f"{a.name}:{a.type.value}={a.default}" for a in app.args)


class DashboardApp(App):
    """A control panel for the stello project this app lives in."""

    CSS = """
    #left { width: 45%; border-right: solid $panel; }
    #right { width: 55%; padding: 0 1; }
    #detail { padding: 1 0; color: $text-muted; }
    #arg-controls { height: auto; max-height: 40%; }
    .arg-row { height: 3; }
    .arg-row Label { width: 16; content-align: left middle; height: 3; }
    #run { margin: 1 0; }
    #output { height: 1fr; border: round $panel; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, theme_name: str = "dark", compact: bool = False) -> None:
        super().__init__()
        self.theme_name = theme_name
        self.compact = compact
        self.apps: list[Application] = []
        self.load_error: str | None = None
        try:
            self.apps = load_manifest(REPO_ROOT).applications
        except Exception as exc:  # surface any manifest problem in the UI, don't crash
            self.load_error = str(exc)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="left"):
                yield DataTable(id="apps", cursor_type="row")
            with Vertical(id="right"):
                yield Static(id="detail")
                yield VerticalScroll(id="arg-controls")
                yield Button("▶ Run", id="run", variant="success")
                yield Log(id="output")
        yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()
        self.title = f"stello · {REPO_ROOT.name}"
        self.sub_title = (
            self.load_error
            if self.load_error
            else f"{len(self.apps)} application(s) in this project"
        )

        table = self.query_one("#apps", DataTable)
        if self.compact:
            table.add_columns("app", "args")
        else:
            table.add_columns("app", "dir", "script", "args")
        for app in self.apps:
            if self.compact:
                table.add_row(app.name, _args_summary(app), key=app.name)
            else:
                table.add_row(app.name, app.dir, app.script, _args_summary(app), key=app.name)

        if self.apps:
            self._render_controls(self.apps[0])
        else:
            self.query_one("#detail", Static).update(
                self.load_error or "No applications defined in this project's stello.yaml."
            )

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

    def _app_by_name(self, name: str) -> Application | None:
        return next((a for a in self.apps if a.name == name), None)

    def _render_controls(self, app: Application) -> None:
        self.selected = app
        self.query_one("#detail", Static).update(
            f"[b]{app.name}[/b]\n{app.dir} → {app.script}"
        )
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

    def _collect_overrides(self, app: Application) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for arg in app.args:
            widget = self.query_one(f"#arg-{arg.name}")
            if isinstance(widget, Checkbox):
                overrides[arg.name] = "true" if widget.value else "false"
            else:
                overrides[arg.name] = widget.value
        return overrides

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self._app_by_name(event.row_key.value)
        if app is not None:
            self._render_controls(app)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "run":
            return
        app = getattr(self, "selected", None)
        if app is None:
            return
        output = self.query_one("#output", Log)
        try:
            argv = resolve_args(app, self._collect_overrides(app))
        except Exception as exc:
            output.write_line(f"! {exc}")
            return
        cmd = ["uv", "run", "--directory", str(app.resolved_dir(REPO_ROOT)), app.script, *argv]
        pretty = " ".join(shlex.quote(part) for part in cmd)
        output.write_line(f"$ {pretty}")
        output.write_line(f"  (dummy) launching {app.name}…")
        output.write_line("  (dummy) exited 0")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello project dashboard.")
    parser.add_argument("--theme", default="dark", help="dark or light")
    parser.add_argument("--compact", action="store_true", help="denser table")
    args = parser.parse_args()
    DashboardApp(theme_name=args.theme, compact=args.compact).run()


if __name__ == "__main__":
    main()
