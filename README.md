# Stello

Publish, share, and run Python applications locally — no infrastructure to deploy.

Stello wraps `git` and `uv` to let teams clone, update, and run each other's Python
apps from a single command line, entirely on the local machine.

## Status

Very early alpha — but it works. You can install stello, initialize projects, and run
their applications today. Expect rough edges and breaking changes.

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

Stello is itself a stello project — its repo root declares a `dashboard` application (a
[Textual](https://textual.textualize.io/) control panel that introspects the project it
lives in). Initialize it as a project, then run it:

```bash
stello init stello https://github.com/nikovacevic/stello.git
stello run dashboard
```

Pass an argument to change the theme:

```bash
stello run dashboard --set theme=light
```

Inspect and update your projects:

```bash
stello projects        # list projects, active one marked with *
stello apps            # list apps in the active project
stello update          # pull the latest main for the active project
```

The dashboard reuses stello's own manifest parser, and its uv project depends on stello
via a `../..` path source — so once cloned into `~/.stello/projects/stello`, it builds
stello from that clone, not from your dev checkout.

## Development

Run from a source checkout without installing:

```bash
uv run stello --help
```

See [`agents/product.md`](agents/product.md) for the product spec and
[`AGENTS.md`](AGENTS.md) for development guidance.
