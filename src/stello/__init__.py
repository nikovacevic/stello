"""Stello — build and distribute tools that run locally."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stello")
except PackageNotFoundError:  # not installed (e.g. running from a bare source tree)
    __version__ = "0.0.0+unknown"
