"""Dogfood entry point for the ``terminal`` app: stello's own Textual TUI.

The implementation lives in :mod:`stello._apps.terminal`, shipped in the package so the
built-in ``stello terminal`` command can launch it directly. This shim lets ``stello run
terminal`` run it as an ordinary stello application, receiving ``--theme`` / ``--compact``
from stello like any other app.
"""

from stello._apps.terminal import main

if __name__ == "__main__":
    main()
