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


# — tool config ————————————————————————————————————————————————————————————————


def test_load_tools(repo):
    (repo / "tools").mkdir()
    (repo / "tools" / "tools.toml").write_text(
        '[[tool]]\nname = "uv"\ncheck = "command -v uv"\n\n'
        '[tool.install]\nmacos = "brew install uv"\nlinux = "curl | sh"\n\n'
        '[[tool]]\nname = "obsidian"\ncheck = "test -d /Applications/Obsidian.app"\n\n'
        '[tool.install]\nmacos = "brew install --cask obsidian"\n'
    )
    tool_list = config.load_tools(repo)
    assert len(tool_list) == 2
    assert tool_list[0].name == "uv"
    assert tool_list[0].install.linux == "curl | sh"
    assert tool_list[1].name == "obsidian"
    assert tool_list[1].install.linux is None


def test_load_tools_missing_file(repo):
    assert config.load_tools(repo) == []


def test_save_and_load_tools_roundtrip(repo):
    (repo / "tools").mkdir()
    tool_list = [
        config.ToolDefinition(
            name="uv",
            check="command -v uv",
            install=config.ToolInstall(macos="brew install uv", linux="curl | sh"),
        ),
        config.ToolDefinition(
            name="obsidian",
            check="test -d /Applications/Obsidian.app",
            install=config.ToolInstall(macos="brew install --cask obsidian"),
        ),
    ]
    config.save_tools(repo, tool_list)
    loaded = config.load_tools(repo)

    assert len(loaded) == 2
    assert loaded[0].name == "uv"
    assert loaded[0].install.macos == "brew install uv"
    assert loaded[0].install.linux == "curl | sh"
    assert loaded[1].name == "obsidian"
    assert loaded[1].install.linux is None
