# Stello

Publish, share, and run Python applications locally — no infrastructure to deploy.

Stello wraps `git` and `uv` to let teams clone, update, and run each other's Python
apps from a single command line, entirely on the local machine.

## Status

Very early alpha — but it works! You can install stello, initialize and upgrade projects,
and run applications. Expect rough edges and breaking changes.

## Getting started

Stello requires [`git`](https://git-scm.com/) and [`uv`](https://docs.astral.sh/uv/) to be
installed on your PATH. With those in place, install stello using `uv` and `git`:

```bash
uv tool install git+https://github.com/nikovacevic/stello.git
```

Run `stello` for a list of commands:

```bash
stello

 Usage: stello [OPTIONS] COMMAND [ARGS]...

 Publish, share, and run Python applications locally — no infrastructure to deploy.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version          Show the version and exit.                                                        │
│ --help             Show this message and exit.                                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────╮
│ install   Clone a remote git repo and install it as a new project.                                   │
│ remove    Remove an initialized project, deleting its local clone.                                   │
│ update    Fetch a project (or all projects) and update its checkout.                                 │
│ run       Run an application from a project via `uv`.                                                │
│ apps      List every application across all projects, as `<project>/<app>`.                          │
│ projects  List initialized projects and the ref each is on.                                          │
│ refs      List the branches and tags available for a project, marking the current one.               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

If the `stello` command isn't found after installing, add uv's bin dir to your PATH, and try again:

```bash
uv tool update-shell
```

After `stello` is installed, the first step is to install a project:

```bash
stello install <project> <git_remote_url|local_git_directory> [--ref <branch|tag|commit>]
```

The project simply needs a `stello.yaml` file at its root, which describes one or more applications:

```yaml
description: The team's shared models.   # optional
applications:
  - name: model
    description: Forecasts revenue.       # optional
    dir: ./apps/model            # uv project root
    script: ./src/model/main.py  # entrypoint, relative to dir
    args:
      - name: scenario
        description: Which scenario to run.  # optional
        type: string
        default: base
      - name: verbose
        type: bool
        default: false
  - name: webapp
    dir: ./apps/ui
    script: ./main.py
```

Descriptions are optional at every level and are surfaced by `stello describe`.

From there, you can list apps and run one:

```bash
stello apps
```
```bash
stello run <project>/<application>
```

To pick up updates, as authors push to the underlying project repo, simply run update:

```bash
stello update <project>
```

We recommend starting by installing the `stello` repo itself, which contains two control planes.

### Run Stello Control Planes on Stello

Stello has two control planes:
1. `stello/terminal`, a [Textual](https://textual.textualize.io/) TUI
2. `stello/dashboard`, a [NiceGUI](https://nicegui.io/) web UI

Both browse your projects and list/launch their apps. Both are stello apps, declared in this repo's `stello.yaml` file, so
you can either stick to the super-light CLI, or run one (or both) of the control planes with ease.

The terminal TUI also manages projects with single keys: `u` updates the highlighted project, `i` installs a new one from
a remote URL (with an optional ref), `r` removes the highlighted project, and `f` lists its branches and tags to switch
between them.

```bash
stello install stello https://github.com/nikovacevic/stello.git
stello run stello/terminal
```

<img width="1628" height="822" alt="stello-terminal" src="https://github.com/user-attachments/assets/2674d3ba-f53c-4e6e-a264-622b979e6268" />

```bash
stello run stello/dashboard
```

<img width="1695" height="1109" alt="stello-dashboard" src="https://github.com/user-attachments/assets/f2761cd4-8aae-4241-8358-015d1a8bca9e" />

Enjoy the control planes. But as a reminder, everything the panels do (and more) is available directly on the CLI:

```bash
stello run <project>/<app>         # run an app
stello apps                        # list every app, as <project>/<app>
stello describe <project>/<app>    # describe an app

stello projects                    # list projects and the ref each is on
stello install <name> <git_url>    # install a new project from a git repo
stello describe <project>          # describe a project (or an app: <project>/<app>)
stello update <project>            # fetch and update a project (stays on current ref)
stello remove <project>            # install a new project from a git repo
```

## Development

Run from a source checkout without installing:

```bash
uv run stello --help
```

The `terminal` and `dashboard` apps reuse stello's own library, and each app's uv project
depends on stello via a `../..` path source — so once cloned into `~/.stello/projects/stello`,
they build stello from that clone, not from your dev checkout.

### Building

Build the sdist and wheel with uv — no virtualenv or extra tooling required:

```bash
uv build
```

The version is derived from git tags by `hatch-vcs`, so build from a checkout that has the
tags present (a shallow clone without them resolves to a `0.0.0`-style dev version).

If you'd rather build without uv — for example on an externally-managed machine (PEP 668)
where you can't install into the system Python — do it inside a standard virtual environment.
A `python3 -m venv` already bundles pip, so you only add the `build` frontend:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip build
python3 -m build
```

To cut a release and publish to PyPI, see [`RELEASE.md`](RELEASE.md).

See [`agents/product.md`](agents/product.md) for the product spec and
[`AGENTS.md`](AGENTS.md) for development guidance.
