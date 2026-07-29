# To do

Planned work, not yet started. Move items into the code (and delete them here) as they're done.

- **CI matrix** — add a `.github/workflows/` GitHub Actions workflow running the test suite
  across Python 3.11–3.14 (documented as intent in `AGENTS.md`, not yet implemented).

- **TUI: clean up background processes on exit** — supervised launches (`core.launch_supervised`)
  are children of the TUI, but on quit they should be gracefully terminated (and potentially
  force-killed if they don't stop) rather than left dangling. See `apps/stello/main.py`.

- **TUI: update projects with a keystroke** — add a binding (e.g. `u`) that runs
  `core.update_project` on the browsed project (and maybe a shortcut for `core.update_all`),
  mirroring the control-plane's Update buttons. See `apps/stello/main.py`.

- **Control-plane: rework the UI** — `apps/control-plane/main.py` is functional but spare and
  clunky. Improve the layout, visual hierarchy, and interaction feel.
