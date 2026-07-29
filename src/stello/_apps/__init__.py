"""Stello's own front-end applications, shipped inside the package.

These modules — the Textual ``terminal`` TUI and the NiceGUI ``dashboard`` — are stello
applications like any other, but they also ship in the wheel so the CLI can launch them
directly (``stello terminal`` / ``stello dashboard``) with no project initialized.

Their heavy UI dependencies (Textual, NiceGUI) are *optional extras* (``stello[terminal]``,
``stello[dashboard]``), so importing this package must stay cheap: do **not** import the
submodules here — they pull in those deps at module load. The CLI imports them lazily and
turns a missing extra into a friendly message.
"""
