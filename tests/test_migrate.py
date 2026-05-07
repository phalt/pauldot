"""Tests for migrate.py — migrating an existing ~/.zshrc into a dotfiles repo."""

import pathlib

import pytest

from pauldot import migrate


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    """Minimal scaffolded repo structure."""
    r = tmp_path / "dotfiles"
    (r / "files").mkdir(parents=True)
    (r / "files" / "aliases.zsh").write_text("# Aliases\n")
    (r / "files" / "zshrc.base").write_text("# Base zsh config\n")
    return r


@pytest.fixture
def home(tmp_path) -> pathlib.Path:
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_migrate_splits_aliases_and_other(home, repo):
    (home / ".zshrc").write_text('export PATH="$HOME/.local/bin:$PATH"\nalias ll="ls -la"\nalias gs="git status"\n')
    result = migrate.migrate(home, repo)

    assert len(result.aliases_added) == 2
    assert result.aliases_skipped == []
    assert result.zshrc_line_count > 0
    assert result.dry_run is False

    aliases_content = (repo / "files" / "aliases.zsh").read_text()
    assert 'alias ll="ls -la"' in aliases_content
    assert 'alias gs="git status"' in aliases_content

    base_content = (repo / "files" / "zshrc.base").read_text()
    assert "export PATH" in base_content


def test_migrate_skips_existing_alias_keys(home, repo):
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -l"\n')
    (home / ".zshrc").write_text('alias ll="ls -la"\nalias gs="git status"\n')

    result = migrate.migrate(home, repo)

    assert len(result.aliases_added) == 1
    assert len(result.aliases_skipped) == 1
    assert result.aliases_skipped[0] == 'alias ll="ls -la"'


def test_migrate_raises_if_no_zshrc(home, repo):
    with pytest.raises(FileNotFoundError, match="No ~/.zshrc found"):
        migrate.migrate(home, repo)


def test_migrate_raises_if_zshrc_is_symlink(home, repo):
    target = home / "real_zshrc"
    target.write_text("# something")
    (home / ".zshrc").symlink_to(target)

    with pytest.raises(ValueError, match="already a symlink"):
        migrate.migrate(home, repo)


def test_migrate_empty_zshrc(home, repo):
    (home / ".zshrc").write_text("")
    result = migrate.migrate(home, repo)
    assert result.aliases_added == []
    assert result.aliases_skipped == []
    assert result.zshrc_line_count == 0


def test_migrate_no_aliases(home, repo):
    (home / ".zshrc").write_text("export EDITOR=vim\nexport LANG=en_US.UTF-8\n")
    result = migrate.migrate(home, repo)
    assert result.aliases_added == []
    base_content = (repo / "files" / "zshrc.base").read_text()
    assert "export EDITOR=vim" in base_content


def test_migrate_dry_run_does_not_write(home, repo):
    original_aliases = (repo / "files" / "aliases.zsh").read_text()
    original_base = (repo / "files" / "zshrc.base").read_text()
    (home / ".zshrc").write_text('export EDITOR=vim\nalias ll="ls -la"\n')

    result = migrate.migrate(home, repo, dry_run=True)

    assert result.dry_run is True
    assert len(result.aliases_added) == 1
    assert result.zshrc_line_count > 0
    assert (repo / "files" / "aliases.zsh").read_text() == original_aliases
    assert (repo / "files" / "zshrc.base").read_text() == original_base


def test_migrate_dry_run_reports_skipped_aliases(home, repo):
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -l"\n')
    (home / ".zshrc").write_text('alias ll="ls -la"\nalias gs="git status"\n')

    result = migrate.migrate(home, repo, dry_run=True)

    assert result.dry_run is True
    assert len(result.aliases_added) == 1
    assert len(result.aliases_skipped) == 1
