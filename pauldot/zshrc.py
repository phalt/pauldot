"""Generation of .zshrc.generated, symlink management, and backup logic."""

import datetime
import pathlib
import typing

import pydantic

# Hardcoded until v0.2 when profile resolution takes over.
ZSHRC_TARGET_REL = ".pauldot/files/zshrc.base"


class ZshrcResult(pydantic.BaseModel):
    action: typing.Literal["created", "backup_replaced", "replaced", "no_op"]
    zshrc: pathlib.Path
    target: pathlib.Path
    backup: pathlib.Path | None = None


def apply_zshrc(home: pathlib.Path, dry_run: bool = False) -> ZshrcResult:
    """Symlink ~/.zshrc to the target, backing up any existing regular file.

    If dry_run is True the filesystem is not modified; the result describes what would happen.
    Raises FileNotFoundError if the target file does not exist (dotfiles repo not initialised).
    """
    zshrc = home / ".zshrc"
    target = home / ZSHRC_TARGET_REL

    if not target.exists():
        raise FileNotFoundError(
            f"Dotfiles not found at {target}.\nRun `pauldot init <repo-url>` to clone your dotfiles repo first."
        )

    if zshrc.is_symlink():
        if zshrc.resolve() == target.resolve():
            return ZshrcResult(action="no_op", zshrc=zshrc, target=target)
        # Points elsewhere — replace it, no backup needed.
        if not dry_run:
            zshrc.unlink()
            zshrc.symlink_to(target)
        return ZshrcResult(action="replaced", zshrc=zshrc, target=target)

    if zshrc.exists():
        # Regular file — back it up before replacing.
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup = zshrc.parent / f".zshrc.bak.{timestamp}"
        if not dry_run:
            zshrc.rename(backup)
            zshrc.symlink_to(target)
        return ZshrcResult(action="backup_replaced", zshrc=zshrc, target=target, backup=backup)

    # Nothing there — create the symlink.
    if not dry_run:
        zshrc.symlink_to(target)
    return ZshrcResult(action="created", zshrc=zshrc, target=target)
