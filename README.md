# Stello

Publish, share, and run Python applications locally — no infrastructure to deploy.

Stello wraps `git` and `uv` to let teams clone, update, and run each other's Python
apps from a single command line, entirely on the local machine.

## Status

Very early alpha — but it works! You can install stello, initialize projects, and run
applications. Expect rough edges and breaking changes.

## Getting started

Stello needs [`git`](https://git-scm.com/) and [`uv`](https://docs.astral.sh/uv/) on your
PATH. With those in place, install stello from git:

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
│ init      Clone a remote git repo as a new project.                                                  │
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

After `stello` is installed, the first step is to init a project:

```bash
stello init <project> <git_remote_url|local_git_directory> [--ref <branch|tag|commit>]
```

The project simply needs a `stello.yaml` file at its root, which describes one or more applications:

```yaml
  applications:
    - name: model
      dir: ./apps/model            # uv project root
      script: ./src/model/main.py  # entrypoint, relative to dir
      args:
        - name: scenario
          type: string
          default: base
        - name: verbose
          type: bool
          default: false
    - name: webapp
      dir: ./apps/ui
      script: ./main.py
```

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

We recommend starting by initializing the `stello` repo itself, which contains two control planes.

### Run Stello Control Planes on Stello

Stello has two control planes:
1. `stello/terminal`, a [Textual](https://textual.textualize.io/) TUI
2. `stello/dashboard`, a [NiceGUI](https://nicegui.io/) web UI

Both browse your projects and list/launch their apps. Both are stello apps, declared in this repo's `stello.yaml` file, so
you can either stick to the super-light CLI, or run one (or both) of the control planes with ease.

The terminal TUI also manages projects' git state with single keys: `u` updates the highlighted project, `i` inits a new
one from a remote URL (with an optional ref), and `r` lists a project's branches and tags to switch between them.

```bash
stello init stello https://github.com/nikovacevic/stello.git
stello run stello/terminal
```

<img alt="stello-control-panel" src="https://github.com/user-attachments/assets/357dd616-4aa8-454e-be18-a43e020146c0" />

```bash
stello run stello/dashboard
```

<img width="1994" height="1095" alt="Screenshot 2026-07-29 at 12 19 08 AM" src="https://github.com/user-attachments/assets/3268baee-d635-46a5-beaa-df237c7e654f" />

Enjoy the control planes. But as a reminder, everything the panels do (and more) is available directly on the CLI:

```bash
stello projects                    # list projects and the ref each is on
stello apps                        # list every app, as <project>/<app>
stello refs stello                 # list a project's branches and tags
stello update stello               # fetch and update one project (stays on its ref)
stello update stello --ref v1.2.0  # switch a project to a branch, tag, or commit
stello update --all                # ...update every project
```

## Development

Run from a source checkout without installing:

```bash
uv run stello --help
```

The `terminal` and `dashboard` apps reuse stello's own library, and each app's uv project
depends on stello via a `../..` path source — so once cloned into `~/.stello/projects/stello`,
they build stello from that clone, not from your dev checkout.

See [`agents/product.md`](agents/product.md) for the product spec and
[`AGENTS.md`](AGENTS.md) for development guidance.
