# Open questions

Unresolved technical gaps in the spec. Each needs a decision before the affected
behavior can be implemented. Move resolved items into `product.md` (or `AGENTS.md` for
dev/tooling decisions) and delete them here.

## Supporting non-Python projects

Git state management is language-agnostic and effectively free — the Python coupling lives
entirely in how apps are *run* (`uv run`, via `stello.uv`). What are the paths to running
non-Python apps?

- **A general runner.** Could `uv.command` / `core.run_app` generalize into a runtime-agnostic
  runner that dispatches on a declared runtime — e.g. an application in `stello.yaml` gains a
  `runtime`/`run` field — so an app could be launched with `go run`, `cargo run`, `node`, etc.
  instead of `uv run`? What is the right shape for that abstraction, and what's the default?
- **Toolchain management.** How far does stello go in *provisioning* toolchains? Options span
  (a) assume the toolchain is already on PATH and only wrap the run command, (b) detect and
  warn on a missing toolchain, (c) actively help users install `go` / `rust` / `node` CLIs
  locally (and if so, how, without owning a package manager per language?).

Needs a decision on the runner abstraction's shape and on how much toolchain management (if
any) is in scope before non-Python support can be designed.
