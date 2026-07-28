import pytest

from stello.errors import ArgumentError
from stello.models import Application
from stello.run import parse_overrides, resolve_args


def make_app():
    return Application.model_validate(
        {
            "name": "model",
            "dir": "./apps/model",
            "script": "./main.py",
            "args": [
                {"name": "scenario", "type": "string", "default": "base"},
                {"name": "retries", "type": "int", "default": 3},
                {"name": "verbose", "type": "bool", "default": False},
            ],
        }
    )


def test_parse_overrides_ok():
    assert parse_overrides(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}
    assert parse_overrides(None) == {}


@pytest.mark.parametrize("item", ["noequals", "=novalue"])
def test_parse_overrides_malformed(item):
    with pytest.raises(ArgumentError):
        parse_overrides([item])


def test_parse_overrides_duplicate():
    with pytest.raises(ArgumentError, match="more than once"):
        parse_overrides(["a=1", "a=2"])


def test_resolve_defaults():
    argv = resolve_args(make_app(), {})
    assert argv == ["--scenario", "base", "--retries", "3"]  # verbose False → omitted


def test_resolve_overrides_and_bool_true():
    argv = resolve_args(make_app(), {"scenario": "stress", "verbose": "true"})
    assert argv == ["--scenario", "stress", "--retries", "3", "--verbose"]


def test_resolve_int_override():
    argv = resolve_args(make_app(), {"retries": "5"})
    assert "--retries" in argv and argv[argv.index("--retries") + 1] == "5"


def test_resolve_unknown_arg():
    with pytest.raises(ArgumentError, match="Unknown argument"):
        resolve_args(make_app(), {"nope": "1"})


def test_resolve_bad_int_value():
    with pytest.raises(ArgumentError, match="Invalid value"):
        resolve_args(make_app(), {"retries": "abc"})


def test_resolve_bad_bool_value():
    with pytest.raises(ArgumentError, match="Invalid value"):
        resolve_args(make_app(), {"verbose": "maybe"})
