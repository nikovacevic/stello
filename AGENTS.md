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
  > ⚠️ **Filename unconfirmed.** `agents/product.md` names this file `conf.yaml` in the
  > requirements but `config.yaml` in the command descriptions. This repo currently
  > assumes **`config.yaml`** — confirm with the product owner and reconcile `product.md`
  > before relying on it.
- **Project git repo** — cloned from a remote the user supplies. Today it works from a
  single branch, `main`, only. Branches and tags (e.g. `beta`, semantic versions) are a
  future concern — don't build for them yet, but don't design in a way that forecloses
  them.
- **`stello.yaml`** — MUST exist at the root of every project repo. It lists the
  applications in that project, each a `name` and a `dir` (relative path to the directory
  `uv` runs it from):
  ```yaml
  applications:
    - name: model
      dir: ./apps/model
    - name: webapp
      dir: ./apps/ui
  ```

## Commands

Most commands act on the **active project** (from the config file); a few operate across
or select projects.

| Command | Behavior |
| --- | --- |
| `stello init <project_name> <remote_git_url>` | Clone the remote into `~/.stello/projects/<project_name>` and set it active. |
| `stello list projects` | List initialized projects — the dirs under `~/.stello/projects` that are valid git repos. |
| `stello open <project_name>` | If `<project_name>` is a valid initialized project, set it active in the config file. |
| `stello update` | `git fetch && git pull` the **active** project's repo. |
| `stello update <project_name>` | Same, for the named project. |
| `stello update --all` | Same, for every initialized project. |
| `stello list` | Read the active project's `stello.yaml` and report the runnable application names. |
| `stello run <application_name>` | Look up the application in the active project's `stello.yaml` and `uv run` it from its `dir`. |

Keep command semantics aligned with `agents/product.md`; if you change behavior here,
update that file too.

## Tech stack

- **Language / packaging:** Python, managed with **`uv`**. Stello is itself a uv-managed
  project and is distributed so it can be run via uv (e.g. `uvx`).
- **CLI framework:** **Typer** — use its type-hint-driven command definitions for the
  `init` / `update` / `list` / `run` commands.
- **Dependencies:** keep stello's own footprint small. Its only required *external*
  tools are `git` and `uv`, which it invokes as subprocesses. Each application in the
  remote repo carries its own dependencies, resolved by uv at run time.

## Conventions

- Invoke `git` and `uv` as subprocesses; surface their errors clearly rather than
  swallowing them. A user without `git` or `uv` installed should get an actionable
  message.
- Never assume the config dir or a project exists — create `~/.stello` (and its
  `projects/` subdir) as needed. Fail gracefully when no project is initialized, when
  the config file names a project that doesn't exist, or when no project is active.
- Validate that a `projects/<name>` directory is a real git repo before treating it as a
  project (this is exactly what `stello list projects` filters on).
- A project repo is only usable if it has a `stello.yaml` at its root — treat a missing
  or malformed `stello.yaml` as a clear, named error, not a crash.
- Don't hardcode paths; derive the config dir from the user's home directory so the
  same logic works on macOS and Linux.
- Prefer plain, scriptable output for the `list` commands so they compose with other
  tools.

## Working in this repo

- The `agents/` directory holds context that grows on an as-needed basis. When you
  learn something durable about the product or design, propose adding it there.
- This is an early-stage project — much is still unbuilt. When a requirement is
  ambiguous or undecided, ask rather than inventing behavior, and keep this file honest
  about what is decided vs. deferred.
