"""Subprocess wrappers for git."""

import pathlib
import subprocess


def clone(url: str, dest: pathlib.Path) -> None:
    """Clone a git repo to dest. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed:\n{result.stderr.strip()}")
