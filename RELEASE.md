# Releasing stello

How to cut a release of stello and publish it to PyPI. This is a maintainer runbook —
users don't need it.

## How versioning works

The **git tag is the single source of truth** for the version. `hatch-vcs` derives the
package version from the most recent `v*` tag at build time, so there is no version string
to bump by hand.

- A clean checkout sitting **exactly on** tag `v0.1.0` builds as `0.1.0`.
- Any distance from the tag or a dirty tree adds a **local version segment**
  (e.g. `0.1.1.dev3+g85c114e9.d20260803`). **PyPI and TestPyPI reject anything with a `+…`
  local segment**, so only a clean, on-tag build is publishable.
- Versions follow [SemVer](https://semver.org/). Pre-releases are allowed (`v0.2.0rc1`
  builds `0.2.0rc1`); local versions are not.

## Prerequisites (one-time)

Trusted Publishing lets CI publish without storing API tokens. Configure it once per index:

1. **PyPI** → account → *Publishing* → add a publisher (or *pending publisher* for the very
   first release, before the project exists):
   - Project: `stello` · Owner: `nikovacevic` · Repo: `stello`
   - Workflow: `release.yml` · Environment: `pypi`
2. **TestPyPI** — repeat the same on <https://test.pypi.org> if you rehearse there.
3. **GitHub** → repo Settings → Environments → create `pypi` (optionally require a reviewer,
   which gates every publish behind a manual approval).

For the **manual** flow you also need an API token from the relevant index
(pypi.org *or* test.pypi.org — they are separate accounts).

---

## Standard flow — GitHub Actions (recommended)

Pushing a `v*` tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml),
which builds on clean runners and publishes the wheel/sdist to PyPI over OIDC, builds the
standalone binaries, and attaches them (plus `SHA256SUMS`) to the GitHub Release.

1. Land everything you want in the release on `main` and make sure it's green.
2. Tag a **clean, committed** commit and push the tag:
   ```bash
   git checkout main && git pull
   git tag -a v0.2.0 -m "Release 0.2.0"
   git push origin v0.2.0
   ```
3. Watch the **Release** workflow run. If the `pypi` environment requires a reviewer,
   approve it.
4. [Verify](#verifying-a-release).

That's it — no local build, and the fresh runner is immune to the stale-`dist/` trap below.

---

## Manual flow (break-glass)

Use this only when CI is unavailable. It hands an API token to your machine, which is exactly
what the CI flow avoids — so keep it as a fallback.

1. **Check out the tag** so the build resolves to a clean version:
   ```bash
   git checkout v0.2.0        # detached HEAD, exactly on the tag
   git status                 # MUST be clean — a dirty tree poisons the version
   ```
2. **Clear `dist/` and build.** `uv build` *adds* to `dist/`, so stale artifacts from an
   earlier build will otherwise be uploaded too:
   ```bash
   rm -rf dist/ && uv build
   ls dist/                   # expect stello-0.2.0* with NO "+..." segment
   ```
3. **Check, then upload.** Username is the literal `__token__`; password is your API token.
   ```bash
   python3 -m twine check dist/*
   python3 -m twine upload dist/*
   ```
   `uv publish --token <token>` works too, if you prefer uv over twine.

## Rehearsing on TestPyPI

Prove the pipeline against the throwaway TestPyPI index before a real release:

```bash
rm -rf dist/ && uv build
python3 -m twine upload --repository testpypi dist/*
```

Use a **test.pypi.org** token, and install back to confirm:

```bash
uv tool install --index https://test.pypi.org/simple/ stello
```

(TestPyPI won't have stello's runtime deps, so resolution may need the real PyPI as an extra
index; this step is about proving upload/download, not a full install.)

---

## Verifying a release

Check the PyPI track:

```bash
uv tool install stello        # or: pipx install stello
stello --version              # should print the tag version, e.g. 0.2.0
```

Check the binary track — run the install script and confirm it fetches the new release,
verifies the checksum, and reports the tag version:

```bash
curl -LsSf https://raw.githubusercontent.com/nikovacevic/stello/main/install.sh | sh
~/.stello/bin/stello --version   # should match the tag, e.g. 0.2.0
```

Pin a specific version if `latest` hasn't propagated yet, and use a throwaway install root
to avoid disturbing your own:

```bash
STELLO_HOME=$(mktemp -d) sh -c 'curl -LsSf https://raw.githubusercontent.com/nikovacevic/stello/main/install.sh | sh -s -- --version 0.2.0'
```

Also confirm the project page shows the new version (<https://pypi.org/project/stello/>) and
that the GitHub Release has the three binaries plus `SHA256SUMS` attached.

## Troubleshooting

- **`400 The use of local versions in '…+g….d…' is not allowed`** — the build wasn't a
  clean, on-tag build. The `+…` segment means either uncommitted changes (dirty tree, the
  `.d<date>` marker) or distance from the tag, **or** you're uploading a stale file from a
  previous build. Fix: `git checkout v<version>`, ensure `git status` is clean,
  `rm -rf dist/ && uv build`, and confirm the filenames read `stello-<version>` with no `+`.
- **Version builds as `0.1.dev<N>` (a "no tag found" fallback)** — `hatch-vcs` can't see the
  tags. Locally, make sure the tag exists and is reachable from HEAD. In CI, the checkout
  needs full history and tags (`fetch-depth: 0`, `fetch-tags: true`), which the workflow
  already sets.
- **`twine upload` uploads the wrong file** — it globs `dist/*` and takes everything there.
  Always `rm -rf dist/` before building a release.
