# Stello

Stello allows teams to publish, share and run Python applications locally without deploying infrastructure.

## Problem statement

Non-technical staff are agentially coding powerful tools that replace older tools, like spreadsheets. Deploying
and distributing those tools still requires infrastructure knowledge, usually in the form of a slow-moving
platform engineering team. However, many of these new tools do not require infrastructure to run. Running a
local version of a financial model, dashboard, or prototype suffices for many teams.

Stello aims to let teams build, share and use tools -- all locally, without needing to solve infrastructure deployment.

## Requirements

Stello should allow a user to list, update, and run Python applications using `uv` and `git` under the hood.

Stello should allow a user to set up one or more projects. Each project has a name and corresponds to a
local `git` repository within Stello's local directory.

Stello is **stateless**: there is no "active" project and no `config.yaml`. Every command that acts on a
project names it explicitly — applications are addressed as `<project>/<app>` — so the same command always
means the same thing and stello is safe to script. The only state stello keeps on disk is the project git
repositories themselves.

On Linux and Mac the local directory should be located within the user's home directory. It should
be called `~/.stello`, containing only `projects/<name>/` (one git repo per project). The location can be
overridden by setting the `STELLO_HOME` environment variable, which is useful for testing and for advanced
users who want to relocate the directory.

Within each Stello project (i.e. `git` repository) there MUST be a `stello.yaml` file in the root directory.
It lists the project's applications. Each application has:

- `name` - the name used to run it.
- `dir` - the uv project root, relative to the repo root. Sets the working directory and is where
  `uv` resolves dependencies (a `pyproject.toml`, or PEP 723 inline metadata in the script).
- `script` - the entrypoint file to run, relative to `dir`.
- `args` - optional list of parameters the application accepts. Each has a `name`, a `type`
  (`string` (default), `int`, or `bool`), and a `default`.

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

Application names within a `stello.yaml` must be unique. If two or more applications share a name, Stello
should reject the manifest with an error like "ambiguous application name: {n} applications share the name
{name}" rather than guessing which one to run.

An application's `args` must match the flags its `script` parses: Stello passes each declared arg to
the script as a CLI flag (see `stello run`).

Stello should eventually support a developer experience, but today the developer will need to manage the
remote `git` repository manually.

Each Stello project's remote `git` repository should work from a single branch named `main`. In the future `git`
branches and tags should be supported, for things like `beta`, semantic versioning, etc.

## Commands

Stello should support the following commands. There is no active project, so every command that acts on a
project names it (or, for `update`, uses `--all`).

#### `stello init <project_name> <remote_git_url>`

Should clone the `git` repo to the local stello directory under the given project name.

For example, `stello init model git@github.com:my-org/my-model.git` should clone the given `git` project into
`~/.stello/projects/model`.

Init should clone the remote's `main` branch explicitly and fail if the remote has no `main` branch. Project
names must be unique: if a project with the given name already exists, init should error rather than overwrite
it. Re-cloning the same remote under a different project name is allowed.

#### `stello projects`

Should list the names of the initialized projects, which is just the names of the directories within
`~/.stello/projects` which are valid `git` repositories.

#### `stello update <project_name>` / `stello update --all`

Should update the `git` repository for a project to the latest `main`. Project checkouts are treated as
read-only mirrors, so update should `git fetch` and then `git reset --hard origin/main` rather than `git pull`
— this avoids merge conflicts if the local working tree has drifted (e.g. from running applications in place).

`stello update <project_name>` updates that one project; `stello update --all` updates every initialized
project. `stello update` with neither a project name nor `--all` is an error (there is no active project to
default to). Combining `--all` with a project name is also an error.

#### `stello apps`

Should list every application across all initialized projects, one per line as `<project>/<app>` — reading each
project's `stello.yaml` (located in the root of its `git` repository). A project whose manifest is missing or
malformed is skipped rather than aborting the whole listing. The output doubles as the set of references
accepted by `stello run`.

#### `stello run <project>/<app> [--set <name>=<value> ...]`

Should read the named project's `stello.yaml`, find the application with the given name, and run it with `uv`
from the application's `dir`, roughly:

```
uv run --directory <dir> <script> <args...>
```

The application reference is always `<project>/<app>` — there is no active project to omit it against. A
reference without exactly one `/` is an error.

Argument values start from each declared arg's `default` and are overridden by `--set <name>=<value>`. A `--set`
name that doesn't match a declared arg is an error. Values are passed to the script as CLI flags:

- `string` / `int` args are passed as `--<name> <value>`.
- `bool` args are passed as `--<name>` when true, and omitted when false.

For example, given a `model` application in the `demo` project, `stello run demo/model --set scenario=stress
--set verbose=true` runs `uv run --directory ./apps/model ./src/model/main.py --scenario stress --verbose`.

Stello uses a plain `uv run` (not `--frozen`), so applications run whether or not they commit a `uv.lock`. Any
lockfile or virtualenv churn a run leaves in the checkout is disposable — `stello update` hard-resets to
`origin/main`.

## Control panels

Stello ships two control-panel UIs — a Textual TUI (`terminal`) and a NiceGUI web dashboard (`dashboard`) —
that browse projects and list/launch their applications. These are **ordinary stello applications, not
built-in commands**: the stello repo is itself a stello project whose `stello.yaml` declares them, so you run
them with `stello run stello/terminal` and `stello run stello/dashboard` after initializing the stello project.
Keeping them as apps keeps the core install light (no Textual/NiceGUI dependency) and demonstrates that stello
runs *any* project's apps, including its own. In the panels, projects are just namespaces to browse — there is
no "open"/active concept.

## Future work

- **Ambient project context (not yet built).** To recover the ergonomics of a default project without
  reintroducing persisted global state, stello may later honor a `STELLO_PROJECT` environment variable (a
  per-shell, explicit, ephemeral context, like `AWS_PROFILE`) and/or let `stello run <app>` omit the project
  when exactly one project is initialized. Neither exists today; `<project>/<app>` is always required.
- **Branches and tags.** Each project's remote works from a single `main` branch today (see below); `beta`,
  semantic versions, etc. are a future concern.

## Dependencies

Stello requires only two main dependencies: `git` for managing state, and `uv` for running Python applications.

Each Python application will have its own set of dependencies, which stello should use `git` and `uv` to help manage.