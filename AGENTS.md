# AGENTS.md

Guidance for agents working in the `stello` repository. For the product vision and
requirements, read [`agents/product.md`](agents/product.md) first — it is the source of
truth for *what* stello does. This file covers *how* to build it.

## What stello is

Stello is a Python CLI that lets teams publish, share, and run Python applications
**locally** — no infrastructure to deploy. It wraps two tools under the hood:

- **`git`** — for fetching and updating the shared repository of applications.
- **`uv`** — for resolving each application's dependencies and running it.

The goal: builders build, users use, all locally.

## Architecture

Stello has two levels of nesting: **projects** (git repos stello manages) and, inside
each, **applications** (runnable Python apps declared in `stello.yaml`).

- **Home directory** — `~/.stello` on macOS and Linux. Stello owns this; the user is
  not expected to edit it by hand. It contains only:
  - `projects/<name>/` — one git repo per project, cloned by `stello install`.
- **No global state** — stello is stateless. There is no active-project pointer and no
  `config.yaml`; every command names the project it acts on (`<project>/<app>`). The
  directory-layout logic lives in `stello.paths` (home dir, `projects/`, `STELLO_HOME`).
- **Project git repo** — cloned from a remote the user supplies (checking out the remote's
  default branch, or `stello install --ref <ref>` to start elsewhere; no particular branch
  name is required). A project tracks a single **ref** — a branch, tag, or commit — held
  as git's own HEAD, so stello keeps no separate record of it:
  - **attached HEAD (a branch)** is *tracked* — a plain `stello update` advances it to
    the remote tip.
  - **detached HEAD (a tag or commit)** is a *pin* — a plain `stello update` still fetches
    but leaves the checkout where it is.

  `stello update <project> --ref <ref>` switches to any branch, tag, or commit; a switched
  branch is attached, a tag/commit is detached. All the ref logic lives in `stello.git`.
- **`stello.yaml`** — MUST exist at the root of every project repo. It lists the
  applications in that project, and may carry an optional top-level `description`. Each
  application has a `name`, an optional `description`, a `dir` (the uv project root, relative
  to the repo root — sets the working dir and where uv resolves deps), a `script` (entrypoint,
  relative to `dir`), and an optional `args` list. Each arg has a `name`, an optional
  `description`, a `type` (`string` (default), `int`, or `bool`), and a `default`. Descriptions
  are surfaced by `stello describe`. Application names within a manifest must be unique.
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

## Commands

Stello is **stateless** — there is no active project. Every command that acts on a project
names it, and applications are addressed as `<project>/<app>`.

| Command | Behavior |
| --- | --- |
| `stello install <project_name> <remote_git_url> [--ref <ref>]` | Clone the remote into `~/.stello/projects/<project_name>`, checking out its default branch (or `--ref`). |
| `stello remove <project_name> [--yes]` | Delete an initialized project's local clone. Prompts for confirmation unless `--yes`/`-y`. |
| `stello apps` | List every application across all projects, one per line as `<project>/<app>`; skip projects with a bad manifest. |
| `stello describe <project>` | Print the project's name, description, current ref, and each application's name and description. |
| `stello describe <project>/<app>` | Print the application's name, description, the project's current ref, `dir`, `script`, and its args (name, description, type, default). |
| `stello run <project>/<app> [--set NAME=VALUE ...]` | Look up `<app>` in `<project>`'s `stello.yaml` and `uv run` it from its `dir`, with declared-arg defaults overridden by `--set`. A ref without exactly one `/` is an error. |
| `stello projects` | List initialized projects, each annotated with the ref it's on: `<project> [<ref>]`. |
| `stello refs <project_name>` | List the branches and tags available on the project's remote (`git ls-remote`), marking the current one with `*`. |
| `stello update <project_name>` | Fetch, then advance the current ref (a tracked branch to its remote tip; a detached pin stays put). |
| `stello update <project_name> --ref <ref>` | Fetch, then switch the checkout to `<ref>` (a branch, tag, or commit), discarding local drift. |
| `stello update --all` | Fetch and advance the current ref of every initialized project (no `--ref`). |

The control panels are **ordinary apps, not commands**: run them with `stello run
stello/terminal` and `stello run stello/dashboard` after `stello install`-ing the stello repo.

Keep command semantics aligned with `agents/product.md`; if you change behavior here,
update that file too.

## Tech stack

- **Language / packaging:** Python, managed with **`uv`**. Stello is itself a uv-managed
  project and is distributed so it can be run via uv (e.g. `uvx`).
- **CLI framework:** **Typer** — use its type-hint-driven command definitions for the
  `init` / `projects` / `update` / `apps` / `run` commands.
- **Dependencies:** keep stello's own footprint small. Its only required *external*
  tools are `git` and `uv`, which it invokes as subprocesses. Each application in the
  remote repo carries its own dependencies, resolved by uv at run time. The `terminal` /
  `dashboard` control panels are **ordinary stello apps** under `apps/`, not built-in
  commands — their heavy UI deps (Textual, NiceGUI) live in each app's own project, so
  they never touch the base `stello` install. The `stello` package ships no UI code.
- **Python version:** `requires-python` is floor-only (`>=3.11`) — do **not** add an upper
  cap preemptively; add `<3.X` only reactively if a real incompatibility (e.g. a lagging
  `pydantic-core` wheel) appears on a newer interpreter. `.python-version` pins a stable
  dev/CI default (3.13) for reproducibility, not prohibition. Coverage on newer Pythons
  should come from a **CI matrix across 3.11–3.14**, not from constraining what users run.
  (This governs only the interpreter Stello itself runs on; each application resolves its
  own Python via its own uv project.)

## Conventions

- Invoke `git` and `uv` as subprocesses; surface their errors clearly rather than
  swallowing them. A user without `git` or `uv` installed should get an actionable
  message.
- Never assume the home dir or a project exists — create `~/.stello` (and its
  `projects/` subdir) as needed. Fail gracefully when no project is initialized or when a
  command names a project that doesn't exist.
- Validate that a `projects/<name>` directory is a real git repo before treating it as a
  project (this is exactly what `stello projects` filters on).
- A project repo is only usable if it has a `stello.yaml` at its root — treat a missing
  or malformed `stello.yaml` as a clear, named error, not a crash.
- Don't hardcode paths; derive the config dir from the user's home directory so the
  same logic works on macOS and Linux.
- Prefer plain, scriptable output for `projects` and `apps` so they compose with other
  tools.

## Working in this repo

- The `agents/` directory holds context that grows on an as-needed basis. When you
  learn something durable about the product or design, propose adding it there.
- This is an early-stage project — much is still unbuilt. When a requirement is
  ambiguous or undecided, ask rather than inventing behavior, and keep this file honest
  about what is decided vs. deferred.
