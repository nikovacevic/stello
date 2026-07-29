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
    ref: Annotated[
        Optional[str],
        typer.Option("--ref", help="Switch the project to this branch, tag, or commit."),
    ] = None,
    all_: Annotated[bool, typer.Option("--all", help="Update every initialized project.")] = False,
) -> None:
    """Fetch a project (or all projects) and update its checkout.

    Without `--ref` a project stays on its current ref: a tracked branch advances to the
    remote tip; a pinned tag or commit stays put. With `--ref` the project switches to the
    named branch, tag, or commit.
    """
    if all_ and project_name:
        raise ArgumentError("Cannot combine --all with a project name.")
    if all_ and ref is not None:
        raise ArgumentError("`--ref` updates a single project; drop --all.")
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
    core.update_project(project_name, ref=ref)
    typer.echo(f"Updated {project_name!r} ({core.current_ref(project_name)}).")


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
    """List initialized projects and the ref each is on."""
    infos = core.list_projects()
    if not infos:
        typer.echo("No projects initialized. Run `stello init <project_name> <remote_git_url>`.", err=True)
        return
    for info in infos:
        # TODO: append " (update available)" when the local HEAD is behind the remote tip.
        typer.echo(f"{info.name} [{info.ref}]")


@app.command()
def refs(
    project_name: Annotated[str, typer.Argument(help="Project whose refs to list.")],
) -> None:
    """List the branches and tags available for a project, marking the current one."""
    listing = core.list_refs(project_name)

    def _line(name: str) -> str:
        return f"* {name}" if name == listing.current else f"  {name}"

    if not listing.branches and not listing.tags:
        typer.echo(f"No branches or tags found for {project_name!r}.", err=True)
        return
    if listing.branches:
        typer.echo("Branches:")
        for name in listing.branches:
            typer.echo(_line(name))
    if listing.tags:
        typer.echo("Tags:")
        for name in listing.tags:
            typer.echo(_line(name))


def run_cli() -> None:
    """Console-script entrypoint: run the app, turning StelloError into a clean message."""
    try:
        app()
    except StelloError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code)


if __name__ == "__main__":
    run_cli()
