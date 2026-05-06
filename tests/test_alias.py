"""Tests for alias add/list logic."""

import pathlib

import pytest
from typer import testing as typer_testing

from pauldot import cli, state

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


def test_alias_add_duplicate_rejected(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\n')
    result = runner.invoke(cli.app, ["alias", "add", "ll", "ls -lh"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_alias_list(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    (repo / "files" / "aliases.zsh").write_text('alias ll="ls -la"\nalias gs="git status"\n')
    result = runner.invoke(cli.app, ["alias", "list"])
    assert result.exit_code == 0
    assert "ll" in result.output
    assert "gs" in result.output


def test_alias_list_empty(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["alias", "list"])
    assert result.exit_code == 0
    assert "No aliases" in result.output
