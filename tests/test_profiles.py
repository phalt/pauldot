"""Tests for profiles.py — profile resolution and extends chain."""

import pathlib

import pytest

from pauldot import profiles


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    """Minimal dotfiles repo with files/ and profiles/ directories."""
    repo_path = tmp_path / "dotfiles"
    (repo_path / "profiles").mkdir(parents=True)
    (repo_path / "files").mkdir()
    return repo_path


def test_resolve_simple_profile(repo):
    """A profile with no extends resolves to itself."""
    (repo / "profiles" / "personal.toml").write_text(
        'zshrc = "files/zshrc.personal"\ntools = ["starship"]\n\n[env]\nEDITOR = "vim"\n'
    )
    result = profiles.resolve(repo, "personal")

    assert result.name == "personal"
    assert result.zshrc_files == [repo / "files" / "zshrc.personal"]
    assert result.tools == ["starship"]
    assert result.env == {"EDITOR": "vim"}


def test_resolve_profile_with_extends(repo):
    """A profile that extends base merges zshrc files, tools, and env."""
    (repo / "profiles" / "base.toml").write_text(
        'zshrc = "files/zshrc.base"\ntools = ["uv"]\n\n[env]\nEDITOR = "vim"\n'
    )
    (repo / "profiles" / "work.toml").write_text(
        'extends = "base"\nzshrc = "files/zshrc.work"\ntools = ["starship", "zed"]\n\n'
        '[env]\nEDITOR = "zed --wait"\nWORK_MODE = "true"\n'
    )
    result = profiles.resolve(repo, "work")

    assert result.name == "work"
    # Parent zshrc first, then child.
    assert result.zshrc_files == [
        repo / "files" / "zshrc.base",
        repo / "files" / "zshrc.work",
    ]
    # Parent tools first, then child.
    assert result.tools == ["uv", "starship", "zed"]
    # Child env wins on conflict.
    assert result.env["EDITOR"] == "zed --wait"
    assert result.env["WORK_MODE"] == "true"


def test_resolve_profile_no_zshrc(repo):
    """A profile with no zshrc entry produces no zshrc_files."""
    (repo / "profiles" / "base.toml").write_text("")
    result = profiles.resolve(repo, "base")
    assert result.zshrc_files == []
    assert result.tools == []
    assert result.env == {}


def test_resolve_extends_parent_no_zshrc(repo):
    """Child inherits parent tools/env even if parent has no zshrc."""
    (repo / "profiles" / "base.toml").write_text('tools = ["uv"]\n')
    (repo / "profiles" / "work.toml").write_text('extends = "base"\nzshrc = "files/zshrc.work"\n')
    result = profiles.resolve(repo, "work")
    assert result.zshrc_files == [repo / "files" / "zshrc.work"]
    assert result.tools == ["uv"]


def test_resolve_missing_profile(repo):
    with pytest.raises(FileNotFoundError, match="pauldot profile list"):
        profiles.resolve(repo, "nonexistent")
