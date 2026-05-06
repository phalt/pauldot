"""Generates a starter dotfiles repo from the bundled scaffold template."""

import importlib.resources
import pathlib
import shutil


def generate(dest: pathlib.Path) -> list[pathlib.Path]:
    """Copy the scaffold template to dest and return the list of created paths.

    Raises FileExistsError if dest exists and is non-empty.
    """
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} already exists and is not empty.")

    template_ref = importlib.resources.files("pauldot").joinpath("templates/scaffold")
    with importlib.resources.as_file(template_ref) as template_path:
        shutil.copytree(template_path, dest, dirs_exist_ok=True)

    return sorted(p for p in dest.rglob("*") if p.is_file())
