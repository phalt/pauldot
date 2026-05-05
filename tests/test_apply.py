"""Tests for the symlink/backup logic in zshrc.py."""

import pathlib

import pytest

from pauldot import zshrc


@pytest.fixture
def home(fake_home) -> pathlib.Path:
    """fake_home with the target zshrc file present."""
    target = fake_home / zshrc.ZSHRC_TARGET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# base zshrc\n")
    return fake_home


def test_fresh_install_creates_symlink(home):
    """No ~/.zshrc exists — symlink is created."""
    result = zshrc.apply_zshrc(home)

    link = home / ".zshrc"
    assert result.action == "created"
    assert link.is_symlink()
    assert link.resolve() == (home / zshrc.ZSHRC_TARGET_REL).resolve()
    assert result.backup is None


def test_regular_file_is_backed_up(home):
    """~/.zshrc is a regular file — it's backed up and replaced with a symlink."""
    link = home / ".zshrc"
    link.write_text("# my old zshrc\n")

    result = zshrc.apply_zshrc(home)

    assert result.action == "backup_replaced"
    assert link.is_symlink()
    assert result.backup is not None
    assert result.backup.exists()
    assert result.backup.read_text() == "# my old zshrc\n"


def test_correct_symlink_is_noop(home):
    """~/.zshrc already points at the right target — no change."""
    link = home / ".zshrc"
    link.symlink_to(home / zshrc.ZSHRC_TARGET_REL)

    result = zshrc.apply_zshrc(home)

    assert result.action == "no_op"
    assert link.is_symlink()
    assert result.backup is None


def test_wrong_symlink_is_replaced(home):
    """~/.zshrc points somewhere else — replaced without a backup."""
    link = home / ".zshrc"
    elsewhere = home / "other_zshrc"
    elsewhere.write_text("# somewhere else\n")
    link.symlink_to(elsewhere)

    result = zshrc.apply_zshrc(home)

    assert result.action == "replaced"
    assert link.is_symlink()
    assert link.resolve() == (home / zshrc.ZSHRC_TARGET_REL).resolve()
    assert result.backup is None


def test_missing_target_raises(fake_home):
    """apply_zshrc raises before touching anything if the target file doesn't exist."""
    link = fake_home / ".zshrc"
    link.write_text("# precious config\n")

    with pytest.raises(FileNotFoundError, match="pauldot init"):
        zshrc.apply_zshrc(fake_home)

    # The original file must be untouched.
    assert not link.is_symlink()
    assert link.read_text() == "# precious config\n"


def test_dry_run_does_not_modify_filesystem(home):
    """dry_run=True never touches the filesystem."""
    link = home / ".zshrc"
    link.write_text("# untouched\n")

    result = zshrc.apply_zshrc(home, dry_run=True)

    assert result.action == "backup_replaced"
    assert not link.is_symlink()
    assert link.read_text() == "# untouched\n"
    # Backup path is described but not created.
    assert result.backup is not None
    assert not result.backup.exists()
