# Stello

Publish, share, and run Python applications locally — no infrastructure to deploy.

Stello wraps `git` and `uv` to let teams clone, update, and run each other's Python
apps from a single command line, entirely on the local machine.

See [`agents/product.md`](agents/product.md) for the product spec and
[`AGENTS.md`](AGENTS.md) for development guidance.

## Status

Early development. The CLI command tree is scaffolded; command behavior is being
implemented incrementally.

## Development

```bash
uv run stello --help
```

## Try it: run stello with stello

Stello is itself a stello project — the repo root has a `stello.yaml` declaring a
`dashboard` application (a [Textual](https://textual.textualize.io/) control panel that
introspects the project it lives in).

First, install `stello` with `uv`:

```bash
uv tool install git+https://github.com/nikovacevic/stello.git
```

You might need to add the `bin` dir to your path with `uv tool update-shell`.

Then run the TUI with `stello`:

```bash
stello init stello https://github.com/nikovacevic/stello.git   # a local path works as a git remote
stello run dashboard
```

The dashboard reuses stello's own manifest parser, and its uv project depends on stello
via a `../..` path source — so when the project is cloned into `~/.stello/projects/stello`,
it builds stello from that clone, not from your dev checkout.

During development you can also launch it directly:

```bash
uv run --directory apps/dashboard main.py --theme light
```
