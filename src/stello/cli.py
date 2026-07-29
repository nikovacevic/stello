"""Stello CLI command tree."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from stello import __version__, config, git, projects as project_ops, run as run_args, uv
from stello.errors import (
    ApplicationNotFoundError,
    ArgumentError,
    NoActiveProjectError,
    ProjectNotFoundError,
    StelloError,
)
from stello.manifest import find_application, load_manifest

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
    available = project_ops.list_projects()
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

    config.set_active_project(selected)
    typer.echo(f"Active project set to {selected!r}.", err=True)
    return selected


def _active_project() -> tuple[str, Path]:
    """Resolve the active project, prompting for a selection if none is set."""
    name = config.active_project()
    if name is None:
        name = _select_project_interactively()
    path = project_ops.project_path(name)
    if not git.is_git_repo(path):
        raise ProjectNotFoundError(
            f"Active project {name!r} is not an initialized git repository ({path}). "
            f"Run `stello open <project_name>` or `stello init`."
        )
    return name, path


@app.command()
def init(
    project_name: Annotated[str, typer.Argument(help="Name for the new local project.")],
    remote_git_url: Annotated[str, typer.Argument(help="Remote git URL to clone (must have a `main` branch).")],
) -> None:
    """Clone a remote git repo as a new project and activate it."""
    project_ops.add_project(project_name, remote_git_url)
    config.set_active_project(project_name)
    typer.echo(f"Initialized project {project_name!r} and set it active.")


@app.command("open")
def open_project(
    project_name: Annotated[str, typer.Argument(help="Project to activate.")],
) -> None:
    """Set the active project."""
    project_ops.require_project(project_name)
    config.set_active_project(project_name)
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
        names = project_ops.list_projects()
        if not names:
            typer.echo("No projects to update.", err=True)
            return
        for name in names:
            git.fetch_and_reset(project_ops.project_path(name))
            typer.echo(f"Updated {name!r}.")
        return

    if project_name:
        path = project_ops.require_project(project_name)
        git.fetch_and_reset(path)
        typer.echo(f"Updated {project_name!r}.")
        return

    name, path = _active_project()
    git.fetch_and_reset(path)
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
    _, path = _active_project()
    manifest = load_manifest(path)
    application = find_application(manifest, application_name)
    if application is None:
        available = ", ".join(a.name for a in manifest.applications) or "(none)"
        raise ApplicationNotFoundError(
            f"No application named {application_name!r}. Available: {available}."
        )

    overrides = run_args.parse_overrides(set_)
    argv = run_args.resolve_args(application, overrides)
    exit_code = uv.run_app(application.resolved_dir(path), application.script, argv)
    raise typer.Exit(exit_code)


@app.command()
def apps() -> None:
    """List the applications in the active project."""
    _, path = _active_project()
    manifest = load_manifest(path)
    if not manifest.applications:
        typer.echo("No applications defined in this project's stello.yaml.", err=True)
        return
    for application in manifest.applications:
        typer.echo(application.name)


@app.command()
def projects() -> None:
    """List initialized projects, marking the active one with `*`."""
    names = project_ops.list_projects()
    if not names:
        typer.echo("No projects initialized. Run `stello init <project_name> <remote_git_url>`.", err=True)
        return
    active = config.active_project()
    for name in names:
        marker = "*" if name == active else " "
        typer.echo(f"{marker} {name}")


def run_cli() -> None:
    """Console-script entrypoint: run the app, turning StelloError into a clean message."""
    try:
        app()
    except StelloError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code)


if __name__ == "__main__":
    run_cli()
