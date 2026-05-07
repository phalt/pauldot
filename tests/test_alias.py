"""Tests for alias add/list logic."""

import pathlib

import pytest
from typer import testing as typer_testing

from pauldot import cli, state, zshrc

runner = typer_testing.CliRunner()


@pytest.fixture
def repo(fake_home) -> pathlib.Path:
    """Minimal dotfiles repo with an aliases.zsh file."""
    repo_path = fake_home / ".pauldot"
    files = repo_path / "files"
    files.mkdir(parents=True)
    (repo_path / "profiles").mkdir()
    (repo_path / "tools").mkdir()
    (repo_path / "pauldot.toml").write_text('[core]\ndefault_profile = "base"\n\n[git]\nauto_commit = false\n')
    (repo_path / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\n')
    (files / "zshrc.base").write_text("# base\n")
    (files / "aliases.zsh").write_text("# aliases\n")
    state.save_state(state.State(active_profile="base", repo_url="git@test"))
    return repo_path


def test_alias_add(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["alias", "add", "ll", "ls -la"])
    assert result.exit_code == 0
    assert "ll" in result.output
    content = (repo / "files" / "aliases.zsh").read_text()
    assert 'alias ll="ls -la"' in content


def test_alias_add_triggers_apply(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    runner.invoke(cli.app, ["alias", "add", "ll", "ls -la"])
    zshrc_path = fake_home / ".zshrc"
    assert zshrc_path.exists()
    assert zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER)
    assert 'alias ll="ls -la"' in zshrc_path.read_text()


def test_alias_add_duplicate_rejected(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\n')
    result = runner.invoke(cli.app, ["alias", "add", "ll", "ls -lh"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_alias_add_with_profile_flag(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["alias", "add", "--profile", "work", "wvpn", "vpn on"])
    assert result.exit_code == 0
    profile_file = repo / "files" / "aliases.work.zsh"
    assert profile_file.exists()
    assert 'alias wvpn="vpn on"' in profile_file.read_text()
    # shared aliases.zsh should be unchanged
    assert "wvpn" not in (repo / "files" / "aliases.zsh").read_text()


def test_alias_add_with_profile_flag_in_generated_content(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    # Add a profile-specific alias for the active profile ("base")
    runner.invoke(cli.app, ["alias", "add", "--profile", "base", "pb", "pauldot"])
    zshrc_path = fake_home / ".zshrc"
    assert zshrc_path.exists()
    assert 'alias pb="pauldot"' in zshrc_path.read_text()


def test_alias_list(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\nalias gs="git status"\n')
    result = runner.invoke(cli.app, ["alias", "list"])
    assert result.exit_code == 0
    assert "ll" in result.output
    assert "gs" in result.output


def test_alias_list_shows_source_column(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\n')
    (repo / "files" / "aliases.base.zsh").write_text('alias pb="pauldot"\n')
    result = runner.invoke(cli.app, ["alias", "list"])
    assert result.exit_code == 0
    assert "shared" in result.output
    assert "base" in result.output
    assert "ll" in result.output
    assert "pb" in result.output


def test_alias_remove_shared(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\nalias gs="git status"\n')
    result = runner.invoke(cli.app, ["alias", "remove", "ll"])
    assert result.exit_code == 0
    assert "ll" in result.output  # confirmation message
    content = (repo / "files" / "aliases.zsh").read_text()
    assert "alias ll" not in content
    assert 'alias gs="git status"' in content


def test_alias_remove_profile(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.base.zsh").write_text('alias lol="git log --oneline"\n')
    result = runner.invoke(cli.app, ["alias", "remove", "lol"])
    assert result.exit_code == 0
    assert "lol" in result.output
    assert "alias lol" not in (repo / "files" / "aliases.base.zsh").read_text()


def test_alias_remove_not_found(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["alias", "remove", "nope"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_alias_remove_with_profile_flag(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.work.zsh").write_text('alias wvpn="vpn on"\n')
    result = runner.invoke(cli.app, ["alias", "remove", "--profile", "work", "wvpn"])
    assert result.exit_code == 0
    assert "alias wvpn" not in (repo / "files" / "aliases.work.zsh").read_text()


def test_alias_remove_triggers_apply(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\n')
    runner.invoke(cli.app, ["alias", "remove", "ll"])
    zshrc_path = fake_home / ".zshrc"
    assert zshrc_path.exists()
    assert "alias ll" not in zshrc_path.read_text()


def test_alias_list_empty(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["alias", "list"])
    assert result.exit_code == 0
    assert "No aliases" in result.output
