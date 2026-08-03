# To do

Planned work, not yet started. Move items into the code (and delete them here) as they're done.

- **CI matrix** — add a `.github/workflows/` GitHub Actions workflow running the test suite
  across Python 3.11–3.14 (documented as intent in `AGENTS.md`, not yet implemented).

- **Improve release and install paths** — the tag-driven release (`release.yml`), PyInstaller
  binaries for macOS/Linux x64, and `install.sh` are in place. Remaining, additive work:
  - **Windows x86_64 target** — add `windows-latest` to the `binaries` matrix in
    `release.yml`, producing `stello-windows-x86_64.exe`, and extend the asset detection in
    `install.sh` (and the new `install.ps1` below).
  - **`install.ps1`** — a PowerShell twin of `install.sh` for Windows (`irm … | iex`): detect
    arch, download the `.exe` and `SHA256SUMS`, verify, install under `%USERPROFILE%\.stello\bin`,
    add it to the user PATH, and warn on missing `git`/`uv`.
  - **Homebrew tap** — a `nikovacevic/homebrew-tap` formula so `brew install nikovacevic/tap/stello`
    works; the formula can declare `git` as a dependency. Automate the formula version/sha bump
    from the release workflow.
  - **macOS notarization** — sign and notarize the macOS binaries (needs an Apple Developer
    account, ~$99/yr) so binaries downloaded via a browser clear Gatekeeper. Not needed for the
    `curl … | sh` path, which escapes the `com.apple.quarantine` bit; document `xattr -d
    com.apple.quarantine` as the interim escape hatch for direct downloads.
  - **Build-provenance attestation** — add `actions/attest-build-provenance` for the release
    artifacts (wheel, sdist, and binaries) for supply-chain integrity; optionally sign
    `SHA256SUMS` with cosign or minisign.

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