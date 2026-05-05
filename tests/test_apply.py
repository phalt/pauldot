"""Tests for the zshrc generation/symlink pipeline and apply.run()."""

import pathlib

import pytest

from pauldot import apply, profiles, state, zshrc

# — fixtures ——————————————————————————————————————————————————————————————————


@pytest.fixture
def repo(fake_home) -> pathlib.Path:
    """A minimal dotfiles repo at fake_home/.pauldot with a base profile."""
    repo_path = fake_home / ".pauldot"
    files = repo_path / "files"
    files.mkdir(parents=True)
    (repo_path / "profiles").mkdir()
    (repo_path / "pauldot.toml").write_text('[core]\ndefault_profile = "base"\n')
    (repo_path / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\n')
    (files / "zshrc.base").write_text("# base\n")
    (files / "aliases.zsh").write_text("# aliases\n")
    return repo_path


@pytest.fixture
def saved_state(fake_home, repo) -> state.State:
    """Write a state.toml pointing at the base profile."""
    s = state.State(active_profile="base", repo_url="git@github.com:test/dotfiles")
    state.save_state(s)
    return s


# — generate_zshrc ————————————————————————————————————————————————————————————


def test_generate_zshrc_sources_profile_files(repo):
    """Generated file sources each zshrc file in order, then aliases."""
    profile = profiles.ResolvedProfile(
        name="base",
        zshrc_files=[repo / "files" / "zshrc.base"],
        tools=[],
        env={},
    )
    generated = zshrc.generate_zshrc(repo, profile)

    content = generated.read_text()
    assert "source" in content
    assert str(repo / "files" / "zshrc.base") in content
    assert str(repo / "files" / "aliases.zsh") in content
    assert ".env.generated" in content


def test_generate_zshrc_parent_before_child(repo):
    """Parent zshrc is sourced before child zshrc."""
    (repo / "files" / "zshrc.work").write_text("# work\n")
    profile = profiles.ResolvedProfile(
        name="work",
        zshrc_files=[repo / "files" / "zshrc.base", repo / "files" / "zshrc.work"],
        tools=[],
        env={},
    )
    generated = zshrc.generate_zshrc(repo, profile)
    content = generated.read_text()

    base_pos = content.index(str(repo / "files" / "zshrc.base"))
    work_pos = content.index(str(repo / "files" / "zshrc.work"))
    assert base_pos < work_pos


def test_generate_zshrc_no_aliases_if_missing(repo):
    """aliases.zsh is not sourced when it doesn't exist."""
    (repo / "files" / "aliases.zsh").unlink()
    profile = profiles.ResolvedProfile(name="base", zshrc_files=[], tools=[], env={})
    generated = zshrc.generate_zshrc(repo, profile)
    content = generated.read_text()
    assert "aliases.zsh" not in content


# — apply_zshrc ————————————————————————————————————————————————————————————————


@pytest.fixture
def target(repo) -> pathlib.Path:
    """A generated target file."""
    profile = profiles.ResolvedProfile(
        name="base",
        zshrc_files=[repo / "files" / "zshrc.base"],
        tools=[],
        env={},
    )
    return zshrc.generate_zshrc(repo, profile)


def test_fresh_install_creates_symlink(fake_home, target):
    result = zshrc.apply_zshrc(fake_home, target)
    link = fake_home / ".zshrc"
    assert result.action == "created"
    assert link.is_symlink()
    assert link.resolve() == target.resolve()
    assert result.backup is None


def test_regular_file_is_backed_up(fake_home, target):
    link = fake_home / ".zshrc"
    link.write_text("# my old zshrc\n")
    result = zshrc.apply_zshrc(fake_home, target)
    assert result.action == "backup_replaced"
    assert link.is_symlink()
    assert result.backup is not None
    assert result.backup.read_text() == "# my old zshrc\n"


def test_correct_symlink_is_noop(fake_home, target):
    link = fake_home / ".zshrc"
    link.symlink_to(target)
    result = zshrc.apply_zshrc(fake_home, target)
    assert result.action == "no_op"
    assert result.backup is None


def test_wrong_symlink_is_replaced(fake_home, target):
    link = fake_home / ".zshrc"
    elsewhere = fake_home / "other"
    elsewhere.write_text("# elsewhere\n")
    link.symlink_to(elsewhere)
    result = zshrc.apply_zshrc(fake_home, target)
    assert result.action == "replaced"
    assert link.resolve() == target.resolve()
    assert result.backup is None


def test_missing_target_raises_before_touching_anything(fake_home):
    link = fake_home / ".zshrc"
    link.write_text("# precious\n")
    with pytest.raises(FileNotFoundError, match="pauldot init"):
        zshrc.apply_zshrc(fake_home, fake_home / "nonexistent")
    assert not link.is_symlink()
    assert link.read_text() == "# precious\n"


def test_dry_run_does_not_modify_filesystem(fake_home, target):
    link = fake_home / ".zshrc"
    link.write_text("# untouched\n")
    result = zshrc.apply_zshrc(fake_home, target, dry_run=True)
    assert result.action == "backup_replaced"
    assert not link.is_symlink()
    assert link.read_text() == "# untouched\n"
    assert result.backup is not None
    assert not result.backup.exists()


# — apply.run() ————————————————————————————————————————————————————————————————


def test_apply_run_creates_symlink(fake_home, repo, saved_state):
    result = apply.run(fake_home)
    link = fake_home / ".zshrc"
    assert result.action == "created"
    assert link.is_symlink()


def test_apply_run_dry_run_no_symlink(fake_home, repo, saved_state):
    result = apply.run(fake_home, dry_run=True)
    link = fake_home / ".zshrc"
    assert result.action == "created"
    assert not link.exists()


def test_apply_run_no_state_raises(fake_home, repo):
    with pytest.raises(FileNotFoundError, match="pauldot init"):
        apply.run(fake_home)
