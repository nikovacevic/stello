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

### Control panels, as apps

Stello has two control panels — `terminal`, a
[Textual](https://textual.textualize.io/) TUI, and `dashboard`, a
[NiceGUI](https://nicegui.io/) web UI — that browse your projects and list/launch their
apps. They aren't special commands: they're just stello applications, declared in stello's
own `stello.yaml`. Running them shows how stello runs *any* project's apps — including its
own — and keeps the core install light (their Textual/NiceGUI deps live with the apps, not
in `stello` itself).

Because stello is stateless, applications are addressed as `<project>/<app>`. So first
initialize stello as a project, then run either panel:

```bash
stello init stello https://github.com/nikovacevic/stello.git
stello run stello/terminal
```

<img alt="stello-control-panel" src="https://github.com/user-attachments/assets/357dd616-4aa8-454e-be18-a43e020146c0" />

```bash
stello run stello/dashboard
```

From either panel you can browse projects and apps, select an app, and run it. Pass args
with `--set` in `terminal` or using the controls in the dashboard:

```bash
stello run stello/terminal --set theme=light
stello run stello/dashboard --set port=9000
```

Everything the panels do is available directly on the CLI:

```bash
stello projects            # list initialized projects
stello apps                # list every app, as <project>/<app>
stello update stello       # pull the latest main for one project
stello update --all        # ...or for every project
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
