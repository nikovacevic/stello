"""Typed models for stello's config and project manifests.

Using pydantic gives schema validation with readable errors, which matters because these
files are often written by hand or by an agent.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from stello.coerce import to_bool, to_int
from stello.naming import validate_name


class Config(BaseModel):
    """Contents of ``~/.stello/config.yaml``.

    The only key is ``project``, naming the active project. Unknown keys are rejected so
    typos surface instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    project: str | None = None


class ArgType(str, Enum):
    """The supported declared types for an application argument."""

    STRING = "string"
    INT = "int"
    BOOL = "bool"


class Arg(BaseModel):
    """A declared argument for an application.

    ``default`` is coerced to match ``type`` so downstream argv construction is simple and
    type-consistent.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    type: ArgType = ArgType.STRING
    default: Any

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_name(value, kind="argument")

    @model_validator(mode="after")
    def _coerce_default(self) -> "Arg":
        if self.type is ArgType.BOOL:
            self.default = to_bool(self.default)
        elif self.type is ArgType.INT:
            self.default = to_int(self.default)
        else:
            self.default = str(self.default)
        return self


class Application(BaseModel):
    """A runnable application declared in a project's stello.yaml."""

    model_config = ConfigDict(extra="forbid")

    name: str
    dir: str
    script: str
    args: list[Arg] = []

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_name(value, kind="application")

    @field_validator("dir", "script")
    @classmethod
    def _safe_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute():
            raise ValueError(f"must be a relative path, got {value!r}")
        if ".." in path.parts:
            raise ValueError(f"must not contain '..', got {value!r}")
        return value

    @model_validator(mode="after")
    def _unique_arg_names(self) -> "Application":
        seen: set[str] = set()
        for arg in self.args:
            if arg.name in seen:
                raise ValueError(f"duplicate argument name {arg.name!r}")
            seen.add(arg.name)
        return self

    def resolved_dir(self, repo_root: Path) -> Path:
        """Absolute path to the application's working directory."""
        return (repo_root / self.dir).resolve()

    def resolved_script(self, repo_root: Path) -> Path:
        """Absolute path to the application's entrypoint script."""
        return (self.resolved_dir(repo_root) / self.script).resolve()


class Manifest(BaseModel):
    """Contents of a project's ``stello.yaml``."""

    model_config = ConfigDict(extra="forbid")

    applications: list[Application] = []

    @model_validator(mode="after")
    def _unique_application_names(self) -> "Manifest":
        counts: dict[str, int] = {}
        for app in self.applications:
            counts[app.name] = counts.get(app.name, 0) + 1
        duplicates = {name: n for name, n in counts.items() if n > 1}
        if duplicates:
            name, n = next(iter(duplicates.items()))
            raise ValueError(
                f"ambiguous application name: {n} applications share the name {name!r}"
            )
        return self
