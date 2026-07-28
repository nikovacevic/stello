# Open questions

Unresolved technical gaps in the spec. Each needs a decision before the affected
behavior can be implemented. Move resolved items into `product.md` and delete them here.

## 1. Running apps pollutes the git working tree, breaking `update`

Applications run from `dir`, which lives inside the project's git checkout. `uv run` can
mutate **tracked** files (notably `uv.lock`) and drop untracked `.venv/` and
`__pycache__/` into the tree. A dirty working tree then makes `stello update`'s `git pull`
fail or produce merge conflicts.

Decisions needed:

- Treat project checkouts as **read-only mirrors** (users don't edit them)? If so, state it.
- `run` should use `uv run --frozen` (or `--locked`) so a run can't dirty `uv.lock`.
- `update` should guarantee a clean fast-forward: `git pull --ff-only`, or
  `git fetch` + `git reset --hard origin/main`, rather than plain `git fetch && git pull`
  (which can create merge commits or fail on divergence — and `pull` already fetches).

## 2. Cloned default branch may not be `main`

The spec mandates a single `main` branch, but `git clone` checks out whatever the remote's
default branch is, which isn't guaranteed to be `main`. `stello init` should explicitly
target `main` (e.g. `git clone --branch main`) or verify/checkout `main` after cloning —
otherwise the single-branch invariant is silently violated.

## 3. Underspecified edge cases

Each needs a one-line rule:

- **Re-init an existing project** — `stello init <name> <url>` when `~/.stello/projects/<name>`
  already exists: overwrite, error, or no-op?
- **Duplicate application names** in one `stello.yaml` — reject the file, or first match wins?
- **No active project** — behavior of `stello list` / `stello run` when `config.yaml` has no
  `project` set (or names a project that no longer exists): clear error vs. crash.
