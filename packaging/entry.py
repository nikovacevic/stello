"""Entry shim for the frozen (PyInstaller) build.

PyInstaller freezes a *script*, not a console-script entry point, so this file just
calls the same ``run_cli`` that the ``stello`` console script does.
"""

from stello.cli import run_cli

if __name__ == "__main__":
    run_cli()
