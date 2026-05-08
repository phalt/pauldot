"""Tests for `pauldot clean` via the CLI."""

import pathlib

import pytest
from typer import testing as typer_testing

from pauldot import cli, state

runner = typer_testing.CliRunner()


@pytest.fixture
def repo(fake_home) -> pathlib.Path:
    repo_path = fake_home / ".pauldot"
    (repo_path / "profiles").mkdir(parents=True)
    (repo_path / "files" / "home").mkdir(parents=True)
    (repo_path / "pauldot.toml").write_text('[core]\ndefault_profile = "base"\n')
    (repo_path / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\ndotfiles = [".gitconfig"]\n')
    (repo_path / "files" / "zshrc.base").write_text("# base\n")
    return repo_path


@pytest.fixture
def saved_state(fake_home, repo) -> state.State:
    s = state.State(active_profile="base", repo_url="git@github.com:test/dotfiles")
    state.save_state(s)
    return s


def test_clean_no_backups(fake_home, repo, saved_state):
    """When no backup files exist, clean reports nothing found."""
    result = runner.invoke(cli.app, ["clean"])
    assert result.exit_code == 0
    assert "No backup files found" in result.output


def test_clean_dry_run_shows_backups_without_deleting(fake_home, repo, saved_state):
    """Default (no --yes) lists backup files but does not delete them."""
    bak = fake_home / ".gitconfig.bak.20240101120000"
    bak.write_text("old content")

    result = runner.invoke(cli.app, ["clean"])

    assert result.exit_code == 0
    assert ".gitconfig.bak.20240101120000" in result.output
    assert "would delete" in result.output
    assert bak.exists(), "dry-run must not delete the file"


def test_clean_yes_deletes_backup(fake_home, repo, saved_state):
    """--yes flag deletes the discovered backup files."""
    bak = fake_home / ".gitconfig.bak.20240101120000"
    bak.write_text("old content")

    result = runner.invoke(cli.app, ["clean", "--yes"])

    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    assert not bak.exists(), "backup must be deleted with --yes"


def test_clean_deletes_multiple_backups(fake_home, repo, saved_state):
    """All backup files for a tracked dotfile are deleted."""
    baks = [
        fake_home / ".gitconfig.bak.20240101120000",
        fake_home / ".gitconfig.bak.20240102090000",
    ]
    for b in baks:
        b.write_text("old")

    result = runner.invoke(cli.app, ["clean", "--yes"])

    assert result.exit_code == 0
    for b in baks:
        assert not b.exists()


def test_clean_covers_zshrc_backups(fake_home, repo, saved_state):
    """Backup files next to ~/.zshrc are also found and deleted."""
    bak = fake_home / ".zshrc.bak.20240101120000"
    bak.write_text("old zshrc")

    result = runner.invoke(cli.app, ["clean", "--yes"])

    assert result.exit_code == 0
    assert not bak.exists()


def test_clean_ignores_unrelated_files(fake_home, repo, saved_state):
    """Files that look similar but are not pauldot backups are not touched."""
    unrelated = fake_home / "notes.bak.txt"
    unrelated.write_text("my notes")
    dotfile_bak = fake_home / ".gitconfig.bak.20240101120000"
    dotfile_bak.write_text("old")

    runner.invoke(cli.app, ["clean", "--yes"])

    assert unrelated.exists(), "unrelated file must be left alone"


def test_clean_dry_run_shows_count(fake_home, repo, saved_state):
    """Dry-run output includes the count of backups found."""
    (fake_home / ".gitconfig.bak.20240101120000").write_text("a")
    (fake_home / ".gitconfig.bak.20240102090000").write_text("b")

    result = runner.invoke(cli.app, ["clean"])

    assert "2 backup(s)" in result.output
    assert "--yes" in result.output
