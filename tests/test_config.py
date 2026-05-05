"""Tests for config.py — pydantic models and pauldot.toml loading."""

import pathlib

import pytest

from pauldot import config


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    """Minimal dotfiles repo directory structure."""
    repo_path = tmp_path / "dotfiles"
    (repo_path / "profiles").mkdir(parents=True)
    (repo_path / "files").mkdir()
    return repo_path


def test_load_pauldot_config(repo):
    (repo / "pauldot.toml").write_text('[core]\ndefault_profile = "work"\n\n[git]\nvisibility = "public"\n')
    cfg = config.load_pauldot_config(repo)
    assert cfg.core.default_profile == "work"
    assert cfg.git.visibility == "public"


def test_load_pauldot_config_defaults(repo):
    (repo / "pauldot.toml").write_text("")
    cfg = config.load_pauldot_config(repo)
    assert cfg.core.default_profile == "personal"
    assert cfg.encryption.enabled is False
    assert cfg.git.auto_commit is True


def test_load_pauldot_config_missing(repo):
    with pytest.raises(FileNotFoundError, match="pauldot.toml"):
        config.load_pauldot_config(repo)


def test_load_profile(repo):
    (repo / "profiles" / "work.toml").write_text(
        'extends = "base"\nzshrc = "files/zshrc.work"\ntools = ["starship", "zed"]\n\n[env]\nEDITOR = "zed --wait"\n'
    )
    p = config.load_profile(repo, "work")
    assert p.extends == "base"
    assert p.zshrc == "files/zshrc.work"
    assert p.tools == ["starship", "zed"]
    assert p.env["EDITOR"] == "zed --wait"


def test_load_profile_defaults(repo):
    (repo / "profiles" / "base.toml").write_text("")
    p = config.load_profile(repo, "base")
    assert p.extends is None
    assert p.zshrc is None
    assert p.tools == []
    assert p.env == {}


def test_load_profile_missing(repo):
    with pytest.raises(FileNotFoundError, match="pauldot profile list"):
        config.load_profile(repo, "nonexistent")


def test_list_profiles(repo):
    for name in ("base", "work", "personal"):
        (repo / "profiles" / f"{name}.toml").write_text("")
    assert config.list_profiles(repo) == ["base", "personal", "work"]


def test_list_profiles_empty(repo):
    assert config.list_profiles(repo) == []


def test_list_profiles_no_dir(tmp_path):
    assert config.list_profiles(tmp_path / "nonexistent") == []
