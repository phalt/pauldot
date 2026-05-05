"""Subprocess wrappers and OS detection. Returns 'macos' or 'linux' only."""

import platform
import typing


def detect_os() -> typing.Literal["macos", "linux"]:
    """Return 'macos' or 'linux'. Raises RuntimeError for anything else."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    raise RuntimeError(f"Unsupported OS: {system}. pauldot runs on macOS and Linux only.")
