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


def test_doctor_initialised_no_zshrc(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    state.save_state(state.State(active_profile="base", repo_url="git@test"))
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "pauldot apply" in result.output


def test_doctor_pauldot_owned_zshrc(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    state.save_state(state.State(active_profile="base", repo_url="git@test"))
    (fake_home / ".zshrc").write_text(zshrc.PAULDOT_HEADER + "\n# content\n")
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "managed by pauldot" in result.output


def test_doctor_symlink_warns_to_migrate(fake_home, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    state.save_state(state.State(active_profile="base", repo_url="git@test"))
    target = fake_home / "some_generated_file"
    target.write_text("# old generated\n")
    (fake_home / ".zshrc").symlink_to(target)
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    assert "symlink" in result.output
    assert "pauldot apply" in result.output
