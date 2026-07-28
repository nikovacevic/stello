"""Wrapper around ``uv run`` for launching applications.

Plain ``uv run`` is used (no ``--frozen``): apps run whether or not they ship a
``uv.lock``, and uv resolves dependencies as needed. Keeping the checkout pristine isn't
required here — ``stello update`` hard-resets to ``origin/main``, so any lock/venv churn a
run leaves behind is disposable. Stdio is inherited so the application is fully interactive.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from stello.errors import UvError

UV = "uv"


def run_app(directory: Path, script: str, args: Sequence[str]) -> int:
    """Run ``script`` (relative to ``directory``) via uv, returning its exit code.

    Roughly ``uv run --directory <directory> <script> <args...>``.
    """
    cmd = [UV, "run", "--directory", str(directory), script, *args]
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError as exc:
        raise UvError("`uv` is not installed or not on your PATH.") from exc
    return result.returncode
