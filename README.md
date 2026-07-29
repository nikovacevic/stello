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

If the `stello` command isn't found afterward, add uv's bin dir to your PATH:

```bash
uv tool update-shell
```

### Try it: run stello with stello

Stello is itself a stello project. Its declares two applications: `terminal`, a
[Textual](https://textual.textualize.io/) TUI control panel, and `stello`, a
[NiceGUI](https://nicegui.io/) browser-based control plane. Both browse projects and
list/launch apps.

First, initialize the project:

```bash
stello init stello https://github.com/nikovacevic/stello.git
```

Then, `stello run` either `terminal` or `stello`:
```bash
stello run terminal
```

<img alt="stello-control-panel" src="https://github.com/user-attachments/assets/357dd616-4aa8-454e-be18-a43e020146c0" />

```bash
stello run stello
```

From either the stello UI or terminal, you can browse projects and apps. You can then select an app and run it. Pass args with `--set`
in `terminal` or using the controls in the stello UI:

```bash
stello run terminal --set theme=light
stello run stello --set port=9000
```

Inspect and update your projects from the terminal or the stello UI

All commands available in the terminal and UI are easy to use directly with the CLI:

```bash
stello projects        # list projects, active one marked with *
stello apps            # list apps in the active project
stello update          # pull the latest main for the active project
```

## Development

Run from a source checkout without installing:

```bash
uv run stello --help
```

The `stello` app reuses stello's own manifest parser, and its uv project depends on stello
via a `../..` path source — so once cloned into `~/.stello/projects/stello`, it builds
stello from that clone, not from your dev checkout.

See [`agents/product.md`](agents/product.md) for the product spec and
[`AGENTS.md`](AGENTS.md) for development guidance.
