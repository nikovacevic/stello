import pytest

from stello.errors import InvalidNameError
from stello.naming import validate_name


@pytest.mark.parametrize("name", ["model", "web-app", "app_2", "ABC", "123"])
def test_valid_names_pass_through(name):
    assert validate_name(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "with space", "../escape", "a/b", "dot.name", "café", "name;rm", "."],
)
def test_invalid_names_raise(name):
    with pytest.raises(InvalidNameError):
        validate_name(name)


def test_error_message_includes_kind():
    with pytest.raises(InvalidNameError, match="project"):
        validate_name("../x", kind="project")
