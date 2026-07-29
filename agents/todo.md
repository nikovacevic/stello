# To do

Planned work, not yet started. Move items into the code (and delete them here) as they're done.

- **CI matrix** — add a `.github/workflows/` GitHub Actions workflow running the test suite
  across Python 3.11–3.14 (documented as intent in `AGENTS.md`, not yet implemented).

- **TUI: clean up background processes on exit** — supervised launches (`core.launch_supervised`)
  are children of the TUI, but on quit they should be gracefully terminated (and potentially
  force-killed if they don't stop) rather than left dangling. See `apps/stello-terminal/main.py`.

- **EXAMPLES.md — end-to-end use-case walkthroughs** — add a top-level `EXAMPLES.md` that
  steps through common workflows narratively, tying together `init`, ref-based development,
  tag versioning, `run`, and `update`. Anchor example: a financial-services team of three that
  needs to vibe-code, share, and run applications — how they initialize their project(s), how
  they develop apps within them (feature branches), how they version them (tags), how they run
  them, and how they update them.

- **Add `stello tidy` command to clean up internal git repo state** - as projects get updated
  to different refs, it's possible that we will end up with messy git state. Investigate whether
  or not that is the case. If it is, make a command that cleans up all the hanging refs, leaving
  only the HEAD state.