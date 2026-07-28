"""Pure argument resolution for ``stello run``.

Turns an application's declared args plus any ``--set name=value`` overrides into the argv
list passed to the script. No filesystem or subprocess work happens here, so it's cheap to
test exhaustively.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from stello.coerce import to_bool, to_int
from stello.errors import ArgumentError
from stello.models import Application, Arg, ArgType


def parse_overrides(items: Sequence[str] | None) -> dict[str, str]:
    """Parse ``--set NAME=VALUE`` strings into a mapping, rejecting malformed input."""
    overrides: dict[str, str] = {}
    for item in items or []:
        name, sep, value = item.partition("=")
        if not sep:
            raise ArgumentError(f"Invalid --set {item!r}: expected NAME=VALUE.")
        name = name.strip()
        if not name:
            raise ArgumentError(f"Invalid --set {item!r}: empty argument name.")
        if name in overrides:
            raise ArgumentError(f"Argument {name!r} set more than once.")
        overrides[name] = value
    return overrides


def resolve_args(app: Application, overrides: dict[str, str]) -> list[str]:
    """Build the argv passed to ``app``'s script: declared defaults, with overrides applied."""
    declared = {arg.name: arg for arg in app.args}
    unknown = [name for name in overrides if name not in declared]
    if unknown:
        known = ", ".join(declared) or "(none)"
        raise ArgumentError(
            f"Unknown argument(s) for {app.name!r}: {', '.join(unknown)}. Declared: {known}."
        )

    argv: list[str] = []
    for arg in app.args:
        value = _value_for(arg, overrides)
        argv.extend(_flagify(arg, value))
    return argv


def _value_for(arg: Arg, overrides: dict[str, str]) -> Any:
    if arg.name not in overrides:
        return arg.default
    raw = overrides[arg.name]
    try:
        if arg.type is ArgType.BOOL:
            return to_bool(raw)
        if arg.type is ArgType.INT:
            return to_int(raw)
        return str(raw)
    except ValueError as exc:
        raise ArgumentError(f"Invalid value for --set {arg.name}={raw!r}: {exc}.") from exc


def _flagify(arg: Arg, value: Any) -> list[str]:
    flag = f"--{arg.name}"
    if arg.type is ArgType.BOOL:
        return [flag] if value else []
    return [flag, str(value)]
