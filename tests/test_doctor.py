"""Tests for `pauldot doctor` via the CLI."""

import pathlib

import pytest
from typer import testing as typer_testing

from pauldot import cli, state, zshrc

runner = typer_testing.CliRunner()


@pytest.fixture
def repo(fake_home) -> pathlib.Path:
    """Minimal dotfiles repo at fake_home/.pauldot."""
    repo_path = fake_home / ".pauldot"
    (repo_path / "profiles").mkdir(parents=True)
    (repo_path / "files").mkdir()
    (repo_path / "tools").mkdir()
    (repo_path / "pauldot.toml").write_text('[core]\ndefault_profile = "base"\n')
    (repo_path / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\n')
    (repo_path / "files" / "zshrc.base").write_text("# base\n")
    return repo_path


def test_doctor_uninitialised(fake_home, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "pauldot init" in result.output


def test_doctor_initialised_no_symlink(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    state.save_state(state.State(active_profile="base", repo_url="git@test"))
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "pauldot apply" in result.output


def test_doctor_symlinked(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    state.save_state(state.State(active_profile="base", repo_url="git@test"))

    generated = repo / zshrc.GENERATED_ZSHRC_REL
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text("# generated\n")
    (fake_home / ".zshrc").symlink_to(generated)

    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "symlinked" in result.output
