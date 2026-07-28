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
