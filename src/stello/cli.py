"""Stello CLI command tree — a thin view over :mod:`stello.core`."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from stello import __version__, core, run as run_ops
from stello.errors import ArgumentError, StelloError

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


@app.command()
def init(
    project_name: Annotated[str, typer.Argument(help="Name for the new local project.")],
    remote_git_url: Annotated[str, typer.Argument(help="Remote git URL to clone (must have a `main` branch).")],
) -> None:
    """Clone a remote git repo as a new project."""
    core.add_project(project_name, remote_git_url)
    typer.echo(f"Initialized project {project_name!r}.")


@app.command()
def update(
    project_name: Annotated[
        Optional[str],
        typer.Argument(help="Project to update."),
    ] = None,
    all_: Annotated[bool, typer.Option("--all", help="Update every initialized project.")] = False,
) -> None:
    """Pull the latest `main` for a project (or all projects)."""
    if all_ and project_name:
        raise ArgumentError("Cannot combine --all with a project name.")
    if not all_ and not project_name:
        raise ArgumentError("Specify a project to update, or pass --all.")

    if all_:
        names = core.update_all()
        if not names:
            typer.echo("No projects to update.", err=True)
            return
        for name in names:
            typer.echo(f"Updated {name!r}.")
        return

    assert project_name is not None
    core.update_project(project_name)
    typer.echo(f"Updated {project_name!r}.")


@app.command()
def run(
    application: Annotated[
        str,
        typer.Argument(metavar="PROJECT/APP", help="Application to run, as `<project>/<app>`."),
    ],
    set_: Annotated[
        Optional[list[str]],
        typer.Option("--set", metavar="NAME=VALUE", help="Override a declared argument. Repeatable."),
    ] = None,
) -> None:
    """Run an application from a project via `uv`."""
    project, app_name = run_ops.parse_app_ref(application)
    overrides = run_ops.parse_overrides(set_)
    exit_code = core.run_app(project, app_name, overrides)
    raise typer.Exit(exit_code)


@app.command()
def apps() -> None:
    """List every application across all projects, as `<project>/<app>`."""
    pairs = core.list_all_apps()
    if not pairs:
        typer.echo("No applications found. Run `stello init <project_name> <remote_git_url>`.", err=True)
        return
    for project, application in pairs:
        typer.echo(f"{project}/{application.name}")


@app.command()
def projects() -> None:
    """List initialized projects."""
    infos = core.list_projects()
    if not infos:
        typer.echo("No projects initialized. Run `stello init <project_name> <remote_git_url>`.", err=True)
        return
    for info in infos:
        typer.echo(info.name)


def run_cli() -> None:
    """Console-script entrypoint: run the app, turning StelloError into a clean message."""
    try:
        app()
    except StelloError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code)


if __name__ == "__main__":
    run_cli()
