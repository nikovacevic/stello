"""Stello TUI — a Textual control panel for your stello projects.

This is one of stello's own applications: the ``terminal`` app in the repo's ``stello.yaml``,
run like any other project's app with ``stello run stello/terminal``. It's a thin view over
stello's own library, which it lists as a dependency, and it:

- browses the initialized projects under ``~/.stello/projects`` (left pane), each shown with
  the git ref it's on as ``name [ref]``,
- lists and launches the applications in whichever project you're browsing (middle pane).

The Run button launches the selected app as a supervised child (via ``core.launch_supervised``)
and streams its output into the log panel, composing its args from the on-screen controls.

It also manages projects' git state, mirroring the ``stello`` CLI: ``u`` updates the
highlighted project (fetch, then advance its current ref), ``i`` opens a dialog to init a new
project from a remote URL (with an optional ref), and ``r`` lists a project's branches and
tags so you can switch to one. These git calls run on worker threads so the UI stays
responsive during a fetch or clone.

It receives its own declared args (``--theme``, ``--compact``) from stello, which is how
stello hands declared args to any application.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, OptionList, Static,
)
from textual.widgets.option_list import Option

from stello import core
from stello.models import Application, ArgType

SELF_SCRIPT = Path(__file__).resolve()


def _args_summary(app: Application) -> str:
    if not app.args:
        return "(no args)"
    return ", ".join(f"{a.name}:{a.type.value}={a.default}" for a in app.args)


class InitScreen(ModalScreen[tuple[str, str, str | None] | None]):
    """Centered dialog to initialize a project: name, git remote URL, and an optional ref.

    Dismisses with ``(name, url, ref_or_None)`` on Create, or ``None`` on Cancel/Escape.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    CSS = """
    InitScreen { align: center middle; }
    #dialog { width: 64; height: auto; padding: 1 2; border: thick $panel; background: $surface; }
    #dialog Label.title { text-style: bold; padding-bottom: 1; }
    #dialog Input { margin-bottom: 1; }
    #dialog-buttons { height: auto; align: right middle; }
    #dialog-buttons Button { margin-left: 2; }
    """

    _FIELDS = ("init-name", "init-url", "init-ref")

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Initialize a project", classes="title")
            yield Input(placeholder="project name", id="init-name")
            yield Input(placeholder="git remote URL", id="init-url")
            yield Input(placeholder="ref — optional, defaults to the remote's default branch", id="init-ref")
            with Horizontal(id="dialog-buttons"):
                yield Button("Create", id="create", variant="success")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#init-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._submit()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter advances through the fields; on the last one it submits.
        idx = self._FIELDS.index(event.input.id)
        if idx < len(self._FIELDS) - 1:
            self.query_one(f"#{self._FIELDS[idx + 1]}", Input).focus()
        else:
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        name = self.query_one("#init-name", Input).value.strip()
        url = self.query_one("#init-url", Input).value.strip()
        ref = self.query_one("#init-ref", Input).value.strip()
        if not name or not url:
            self.app.notify("Name and git remote URL are required.", severity="warning")
            return
        self.dismiss((name, url, ref or None))


class RefsScreen(ModalScreen[str | None]):
    """Centered dialog listing a project's branches and tags; ENTER switches to one.

    The current ref is marked with ``*`` and pre-highlighted. Refs are read from the remote
    (``core.list_refs`` → ``git ls-remote``) in a worker, so the dialog opens on a brief
    "loading" state rather than blocking. Dismisses with the chosen ref, or ``None``.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    CSS = """
    RefsScreen { align: center middle; }
    #dialog { width: 56; height: auto; max-height: 80%; padding: 1 2; border: thick $panel; background: $surface; }
    #dialog Label.title { text-style: bold; padding-bottom: 1; }
    #dialog Label.hint { color: $text-muted; padding-top: 1; }
    #refs { height: auto; max-height: 20; }
    """

    def __init__(self, project: str) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Refs · {self.project}", classes="title")
            yield OptionList(Option("loading refs …", disabled=True), id="refs")
            yield Label("↑/↓ to navigate · ENTER to switch · Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        """Fetch the ref list off the UI thread (ls-remote hits the network)."""
        try:
            listing = core.list_refs(self.project)
            self.app.call_from_thread(self._populate, listing, None)
        except Exception as exc:
            self.app.call_from_thread(self._populate, None, str(exc))

    def _populate(self, listing: "core.RefListing | None", error: str | None) -> None:
        option_list = self.query_one("#refs", OptionList)
        option_list.clear_options()
        if error is not None:
            option_list.add_option(Option(f"! {error}", disabled=True))
            return
        assert listing is not None
        if not listing.branches and not listing.tags:
            option_list.add_option(Option("(no refs found)", disabled=True))
            return

        highlight: int | None = None
        index = 0

        def add_group(title: str, refs: list[str]) -> None:
            nonlocal index, highlight
            if not refs:
                return
            option_list.add_option(Option(title, disabled=True))  # section header
            index += 1
            for ref in refs:
                mark = "* " if ref == listing.current else "  "
                option_list.add_option(Option(f"{mark}{ref}", id=ref))
                if ref == listing.current:
                    highlight = index
                index += 1

        add_group("Branches", listing.branches)
        add_group("Tags", listing.tags)
        if highlight is not None:
            option_list.highlighted = highlight
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


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
        ("u", "update_project", "Update"),
        ("i", "init_project", "Init"),
        ("r", "show_refs", "Refs"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, theme_name: str = "dark", compact: bool = False) -> None:
        super().__init__()
        self.theme_name = theme_name
        self.compact = compact
        self.projects: list[core.ProjectInfo] = []
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
                yield Label("Projects", classes="pane-title")
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
        self.title = "stello"

        self.query_one("#projects", DataTable).add_columns("project")
        apps_table = self.query_one("#apps", DataTable)
        if self.compact:
            apps_table.add_columns("app", "args")
        else:
            apps_table.add_columns("app", "dir", "script", "args")

        # Stream supervised-app output regardless of whether a project exists yet, so the
        # panel keeps working after a project is initialized at runtime.
        self.set_interval(0.5, self._stream_logs)
        self._refresh_projects()

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

    def _refresh_projects(self, select: str | None = None) -> None:
        """Reload the project list (names + current ref) and show one of them.

        Called on mount and after any update/init/switch, so the ``[ref]`` shown next to each
        project stays current. Selects ``select`` if given, else keeps the current project,
        else the first.
        """
        self.projects = core.list_projects()
        table = self.query_one("#projects", DataTable)
        table.clear()
        for info in self.projects:
            table.add_row(f"{info.name} [{info.ref}]", key=info.name)

        if not self.projects:
            self.current_project = None
            self.current_project_path = None
            self.apps = []
            self._populate_apps()
            self.query_one("#arg-controls", VerticalScroll).remove_children()
            self.sub_title = "no initialized projects"
            self.query_one("#detail", Static).update(
                "No projects initialized. Press `i` to initialize one."
            )
            return

        names = [info.name for info in self.projects]
        target = select if select in names else self.current_project
        if target not in names:
            target = names[0]
        # Reload directly (not just via the cursor move) so a same-project ref switch still
        # refreshes the apps/detail; the highlight event that _move_cursor triggers is then a
        # no-op because current_project already matches.
        self._load_project(target)
        self._move_cursor("#projects", names.index(target))

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._run_selected()
        elif event.button.id == "stop":
            self._stop_selected()

    # --- update -----------------------------------------------------------

    def action_update_project(self) -> None:
        """`u` — fetch the highlighted project and advance its current ref."""
        name = self.current_project
        if not name:
            self._notify("No project highlighted to update.")
            return
        self._notify(f"Updating {name!r} …")
        self.query_one("#output", Log).write_line(f"· updating {name!r} …")
        self._run_update(name, None)

    @work(thread=True)
    def _run_update(self, name: str, ref: str | None) -> None:
        """Run the (blocking) git fetch/checkout off the UI thread."""
        try:
            core.update_project(name, ref=ref)
            self.call_from_thread(self._on_update_done, name, None)
        except Exception as exc:  # surface git/manifest failures without crashing the TUI
            self.call_from_thread(self._on_update_done, name, str(exc))

    def _on_update_done(self, name: str, error: str | None) -> None:
        output = self.query_one("#output", Log)
        if error:
            output.write_line(f"  ! update failed: {error}")
            self._notify(f"Update failed: {error}")
            return
        current = core.current_ref(name)
        output.write_line(f"  updated {name!r} ({current})")
        self._notify(f"Updated {name!r} ({current}).")
        self._refresh_projects(select=name)

    # --- init -------------------------------------------------------------

    def action_init_project(self) -> None:
        """`i` — open the init dialog, then clone the given remote as a new project."""
        self.push_screen(InitScreen(), self._on_init_result)

    def _on_init_result(self, result: tuple[str, str, str | None] | None) -> None:
        if not result:
            return
        name, url, ref = result
        self._notify(f"Initializing {name!r} …")
        at_ref = f" at {ref}" if ref else ""
        self.query_one("#output", Log).write_line(f"· initializing {name!r} from {url}{at_ref} …")
        self._run_init(name, url, ref)

    @work(thread=True)
    def _run_init(self, name: str, url: str, ref: str | None) -> None:
        """Run the (blocking) clone/checkout off the UI thread."""
        try:
            core.add_project(name, url, ref=ref)
            self.call_from_thread(self._on_init_done, name, None)
        except Exception as exc:  # bad name/url/ref — core cleans up a partial checkout
            self.call_from_thread(self._on_init_done, name, str(exc))

    def _on_init_done(self, name: str, error: str | None) -> None:
        output = self.query_one("#output", Log)
        if error:
            output.write_line(f"  ! init failed: {error}")
            self._notify(f"Init failed: {error}")
            return
        current = core.current_ref(name)
        output.write_line(f"  initialized {name!r} ({current})")
        self._notify(f"Initialized {name!r} ({current}).")
        self._refresh_projects(select=name)

    # --- refs -------------------------------------------------------------

    def action_show_refs(self) -> None:
        """`r` — pick a branch/tag for the highlighted project and switch to it."""
        name = self.current_project
        if not name:
            self._notify("No project highlighted.")
            return
        self.push_screen(RefsScreen(name), self._on_ref_chosen)

    def _on_ref_chosen(self, ref: str | None) -> None:
        name = self.current_project
        if not ref or not name:
            return
        if ref == core.current_ref(name):
            self._notify(f"Already on {ref}.")
            return
        self._notify(f"Switching {name!r} to {ref} …")
        self.query_one("#output", Log).write_line(f"· switching {name!r} to {ref} …")
        self._run_update(name, ref)

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

        if self._would_relaunch_tui(app):
            output.write_line("  (skipped) refusing to launch the terminal TUI from itself")
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

    def _would_relaunch_tui(self, app: Application) -> bool:
        """True if launching ``app`` would start another instance of this same TUI."""
        if self.current_project_path is None:
            return False
        try:
            return app.resolved_script(self.current_project_path) == SELF_SCRIPT
        except Exception:
            return False

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


def run(theme: str = "dark", compact: bool = False) -> None:
    """Launch the Textual TUI."""
    StelloTUI(theme_name=theme, compact=compact).run()


def main() -> None:
    """argparse entry point for running this module as a stello application."""
    parser = argparse.ArgumentParser(description="Stello project control panel.")
    parser.add_argument("--theme", default="dark", help="dark or light")
    parser.add_argument("--compact", action="store_true", help="denser tables")
    args = parser.parse_args()
    run(theme=args.theme, compact=args.compact)


if __name__ == "__main__":
    main()
