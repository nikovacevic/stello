# PyInstaller spec for the standalone `stello` binary.
#
# Build (from the repo root):
#     uv run --group build pyinstaller packaging/stello.spec \
#         --distpath dist/bin --workpath build/pyinstaller --noconfirm
#
# Produces a single self-contained executable at dist/bin/stello (stello.exe on Windows).
# copy_metadata('stello') bundles the package's .dist-info so importlib.metadata — and thus
# `stello --version` — resolves to the real version instead of the 0.0.0 fallback.

import os

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("stello")

# SPECPATH is the directory of this spec file, injected by PyInstaller — so the entry
# shim resolves the same no matter which directory the build is launched from.
entry = os.path.join(SPECPATH, "entry.py")

a = Analysis(
    [entry],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="stello",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # build for the host arch; the CI matrix covers each target
    codesign_identity=None,
    entitlements_file=None,
)
