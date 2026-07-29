"""Stello CLI command tree — a thin view over :mod:`stello.core`."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Annotated, Optional

import typer

from stello import __version__, core, run as run_ops
from stello.errors import (
    ArgumentError,
    MissingExtraError,
    NoActiveProjectError,
    ProjectNotFoundError,
    StelloError,
)

app = typer.Typer(
    name="stello",
    help="Publish, share, and run Python applications locally — no infrastructure to deploy.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"stello {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show the version and exit."),
    ] = False,
) -> None:
    """Stello."""


def _select_project_interactively() -> str:
    """Prompt the user to pick an initialized project, then make it active."""
    available = [p.name for p in core.list_projects()]
    if not available:
        raise NoActiveProjectError(
            "No active project is set and none are initialized. "
            "Run `stello init <project_name> <remote_git_url>` to create one."
        )
    typer.echo("No active project is set. Available projects:", err=True)
    for index, name in enumerate(available, start=1):
        typer.echo(f"  {index}. {name}", err=True)
    choice = typer.prompt("Select a project by name or number").strip()

    if choice.isdigit():
        index = int(choice)
        if not 1 <= index <= len(available):
            raise ProjectNotFoundError(f"No project number {index}.")
        selected = available[index - 1]
    elif choice in available:
        selected = choice
    else:
        raise ProjectNotFoundError(f"No initialized project named {choice!r}.")

    core.set_active(selected)
    typer.echo(f"Active project set to {selected!r}.", err=True)
    return selected


def _active_project() -> str:
    """Resolve the active project name, prompting for a selection if none is set."""
    name = core.active_project()
    if name is None:
        name = _select_project_interactively()
    core.project_path(name)  # validates it's still an initialized project
    return name


@app.command()
def init(
    project_name: Annotated[str, typer.Argument(help="Name for the new local project.")],
    remote_git_url: Annotated[str, typer.Argument(help="Remote git URL to clone (must have a `main` branch).")],
) -> None:
    """Clone a remote git repo as a new project and activate it."""
    core.add_project(project_name, remote_git_url)
    typer.echo(f"Initialized project {project_name!r} and set it active.")


@app.command("open")
def open_project(
    project_name: Annotated[str, typer.Argument(help="Project to activate.")],
) -> None:
    """Set the active project."""
    core.set_active(project_name)
    typer.echo(f"Active project set to {project_name!r}.")


@app.command()
def update(
    project_name: Annotated[
        Optional[str],
        typer.Argument(help="Project to update. Defaults to the active project."),
    ] = None,
    all_: Annotated[bool, typer.Option("--all", help="Update every initialized project.")] = False,
) -> None:
    """Pull the latest `main` for a project (or all projects)."""
    if all_ and project_name:
        raise ArgumentError("Cannot combine --all with a project name.")

    if all_:
        names = core.update_all()
        if not names:
            typer.echo("No projects to update.", err=True)
            return
        for name in names:
            typer.echo(f"Updated {name!r}.")
        return

    name = project_name or _active_project()
    core.update_project(name)
    typer.echo(f"Updated {name!r}.")


@app.command()
def run(
    application_name: Annotated[str, typer.Argument(help="Application to run, from the active project's stello.yaml.")],
    set_: Annotated[
        Optional[list[str]],
        typer.Option("--set", metavar="NAME=VALUE", help="Override a declared argument. Repeatable."),
    ] = None,
) -> None:
    """Run an application from the active project via `uv`."""
    name = _active_project()
    overrides = run_ops.parse_overrides(set_)
    exit_code = core.run_app(name, application_name, overrides)
    raise typer.Exit(exit_code)


@app.command()
def apps() -> None:
    """List the applications in the active project."""
    applications = core.apps_for(_active_project())
    if not applications:
        typer.echo("No applications defined in this project's stello.yaml.", err=True)
        return
    for application in applications:
        typer.echo(application.name)


@app.command()
def projects() -> None:
    """List initialized projects, marking the active one with `*`."""
    infos = core.list_projects()
    if not infos:
        typer.echo("No projects initialized. Run `stello init <project_name> <remote_git_url>`.", err=True)
        return
    for info in infos:
        marker = "*" if info.is_active else " "
        typer.echo(f"{marker} {info.name}")


def _load_app(module_name: str, extra: str, package: str) -> ModuleType:
    """Import a bundled UI app module, or raise a friendly 'install the extra' error.

    Only a missing *extra* dependency (``package``) is turned into ``MissingExtraError``; an
    ImportError from anything else is a real bug and re-raised as a normal traceback.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        failed = exc.name or ""
        if failed == package or failed.startswith(f"{package}."):
            raise MissingExtraError(
                f"The {extra!r} feature isn't installed. Install it with:\n"
                f'    uv tool install "stello[{extra}]"\n'
                f"(in a dev checkout: uv run --extra {extra} stello {extra})"
            ) from exc
        raise


@app.command()
def terminal(
    theme: Annotated[str, typer.Option(help="Color theme: dark or light.")] = "dark",
    compact: Annotated[bool, typer.Option(help="Denser tables.")] = False,
) -> None:
    """Launch the Textual TUI control panel (no project required)."""
    _load_app("stello._apps.terminal", "terminal", "textual").run(theme=theme, compact=compact)


@app.command()
def dashboard(
    port: Annotated[int, typer.Option(help="Port to serve the web UI on.")] = 8080,
    theme: Annotated[str, typer.Option(help="Color theme: dark or light.")] = "dark",
) -> None:
    """Launch the NiceGUI web dashboard (no project required)."""
    _load_app("stello._apps.dashboard", "dashboard", "nicegui").run(port=port, theme=theme)


def run_cli() -> None:
    """Console-script entrypoint: run the app, turning StelloError into a clean message."""
    try:
        app()
    except StelloError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code)


if __name__ == "__main__":
    run_cli()
