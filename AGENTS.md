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

- **Config directory** — `~/.stello` on macOS and Linux. Stello owns this; the user is
  not expected to edit it by hand. It contains:
  - `projects/<name>/` — one git repo per project, cloned by `stello init`.
  - a top-level config file naming the **active project** (see below).
- **Active-project config** — a single YAML file at the root of `~/.stello` that records
  which project is active:
  ```yaml
  project: model  # active project → ~/.stello/projects/model (a git repo)
  ```
- **Project git repo** — cloned from a remote the user supplies. Today it works from a
  single branch, `main`, only. Branches and tags (e.g. `beta`, semantic versions) are a
  future concern — don't build for them yet, but don't design in a way that forecloses
  them.
- **`stello.yaml`** — MUST exist at the root of every project repo. It lists the
  applications in that project. Each application has a `name`, a `dir` (the uv project
  root, relative to the repo root — sets the working dir and where uv resolves deps), a
  `script` (entrypoint, relative to `dir`), and an optional `args` list. Each arg has a
  `name`, a `type` (`string` (default), `int`, or `bool`), and a `default`. Application
  names within a manifest must be unique.
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

## Commands

Most commands act on the **active project** (from the config file); a few operate across
or select projects.

| Command | Behavior |
| --- | --- |
| `stello init <project_name> <remote_git_url>` | Clone the remote's `main` into `~/.stello/projects/<project_name>` and set it active. |
| `stello projects` | List initialized projects (dirs under `~/.stello/projects` that are valid git repos), marking the active one with `*`. |
| `stello open <project_name>` | If `<project_name>` is a valid initialized project, set it active in the config file. |
| `stello update` | Update the **active** project to `origin/main` (`git fetch` + `reset --hard`). |
| `stello update <project_name>` | Same, for the named project. |
| `stello update --all` | Same, for every initialized project. |
| `stello apps` | Read the active project's `stello.yaml` and report the runnable application names. |
| `stello run <application_name> [--set NAME=VALUE ...]` | Look up the application in the active project's `stello.yaml` and `uv run` it from its `dir`, with declared-arg defaults overridden by `--set`. |
| `stello terminal [--theme ...] [--compact]` | Launch stello's built-in Textual TUI control panel in-process. No active project required; needs the `terminal` extra. |
| `stello dashboard [--port ...] [--theme ...]` | Launch stello's built-in NiceGUI web dashboard in-process. No active project required; needs the `dashboard` extra. |

Keep command semantics aligned with `agents/product.md`; if you change behavior here,
update that file too.

## Tech stack

- **Language / packaging:** Python, managed with **`uv`**. Stello is itself a uv-managed
  project and is distributed so it can be run via uv (e.g. `uvx`).
- **CLI framework:** **Typer** — use its type-hint-driven command definitions for the
  `init` / `projects` / `open` / `update` / `apps` / `run` commands.
- **Dependencies:** keep stello's own footprint small. Its only required *external*
  tools are `git` and `uv`, which it invokes as subprocesses. Each application in the
  remote repo carries its own dependencies, resolved by uv at run time. The built-in
  `terminal` / `dashboard` panels ship in the package (`stello._apps`), but their heavy UI
  deps (Textual, NiceGUI) are **optional extras** — `stello[terminal]`, `stello[dashboard]`
  — so the base install stays lean. Those same modules also back the dogfood `terminal` /
  `stello` apps under `apps/`, which are thin shims that import from `stello._apps`.
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
- Never assume the config dir or a project exists — create `~/.stello` (and its
  `projects/` subdir) as needed. Fail gracefully when no project is initialized, when
  the config file names a project that doesn't exist, or when no project is active.
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
