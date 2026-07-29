"""Dogfood entry point for the ``stello`` app: stello's own NiceGUI dashboard.

The implementation lives in :mod:`stello._apps.dashboard`, shipped in the package so the
built-in ``stello dashboard`` command can launch it directly. This shim lets ``stello run
stello`` run it as an ordinary stello application, receiving ``--port`` / ``--theme`` from
stello like any other app.
"""

from stello._apps.dashboard import main

if __name__ in {"__main__", "__mp_main__"}:
    main()
