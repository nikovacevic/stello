"""Value coercion shared by manifest parsing and `--set` override handling.

Both a declared ``default`` in stello.yaml and a ``--set`` value on the command line must
be turned into a typed value. These helpers give both paths identical semantics. They
raise ``ValueError`` on bad input; callers wrap that in the appropriate ``StelloError``.
"""

from __future__ import annotations

from typing import Any


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"expected a boolean (true/false), got {value!r}")


def to_int(value: Any) -> int:
    # bool is a subclass of int; reject it so `true` isn't silently read as 1.
    if isinstance(value, bool):
        raise ValueError(f"expected an integer, got boolean {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise ValueError(f"expected an integer, got {value!r}")
