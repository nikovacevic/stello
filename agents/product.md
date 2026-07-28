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

Stello should allow a user to step up one or more projects. Each project has a name and corresponds to a
local `git` repository within Stello's local configuration directory. The only additional configuration
file within that local configuration directory should be `config.yaml`. The `config.yaml` file should take the
following format:

```yaml
project: model # name of active project (corresponds to ~/.stello/projects/model, which should be a git repo)
```

On Linux and Mac the local configuration directory should be located within the user's home directory. It should
be called `~/.stello`. The location can be overridden by setting the `STELLO_HOME` environment variable, which is
useful for testing and for advanced users who want to relocate the config directory.

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

Stello should support the following commands. Commands that require an active project (`list`, `run`, and
`update` with no arguments) should, when no project is active, prompt the user to select an initialized
project or to run `stello init`.

### `stello init <project_name> <remote_git_url>`

Should clones the `git` repo to the local stello directory under the given project name, and activates it.

For example, `stello init model git@github.com:my-org/my-model.git` should clone the given `git` project into
`~/.stello/projects/model`, and set `project: model` in `config.yaml`.

Init should clone the remote's `main` branch explicitly and fail if the remote has no `main` branch. Project
names must be unique: if a project with the given name already exists, init should error rather than overwrite
it. Re-cloning the same remote under a different project name is allowed.

### `stello list projects`

Should list the names of the initialized projects, which is just the names of the directories within
`~/.stello/projects` which are valid `git` repositories.

### `stello open <project_name>`

Should check the list of valid, initialized projects and set `project: <project_name>` in `config.yaml` if the
given project name is valid.

### `stello update`

Should update the `git` repository for the active project to the latest `main`. Project
checkouts are treated as read-only mirrors, so update should `git fetch` and then
`git reset --hard origin/main` rather than `git pull` — this avoids merge conflicts if the
local working tree has drifted (e.g. from running applications in place).

`stello update --all` should update all projects.

`stello update <project_name>` should update the project of the given name.

### `stello list`

Should read the `stello.yaml` file for the active project (located in the root of its `git` repository) and report
back the application names available to run.

### `stello run <application_name> [--set <name>=<value> ...]`

Should read the `stello.yaml` file for the active project, find the application with the given name, and run it
with `uv` from the application's `dir`, roughly:

```
uv run --directory <dir> <script> <args...>
```

Argument values start from each declared arg's `default` and are overridden by `--set <name>=<value>`. A `--set`
name that doesn't match a declared arg is an error. Values are passed to the script as CLI flags:

- `string` / `int` args are passed as `--<name> <value>`.
- `bool` args are passed as `--<name>` when true, and omitted when false.

For example, given the `model` application above, `stello run model --set scenario=stress --set verbose=true` runs
`uv run --directory ./apps/model ./src/model/main.py --scenario stress --verbose`.

Stello uses a plain `uv run` (not `--frozen`), so applications run whether or not they commit a `uv.lock`. Any
lockfile or virtualenv churn a run leaves in the checkout is disposable — `stello update` hard-resets to
`origin/main`.

## Dependencies

Stello requires only two main dependencies: `git` for managing state, and `uv` for running Python applications.

Each Python application will have its own set of dependencies, which stello should use `git` and `uv` to help manage.