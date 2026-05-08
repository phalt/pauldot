"""Tests for zshrc.py — content generation and plain-file write logic."""

import pathlib

import pytest

from pauldot import profiles, zshrc

# — fixtures ——————————————————————————————————————————————————————————————————


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    repo_path = tmp_path / "dotfiles"
    files = repo_path / "files"
    files.mkdir(parents=True)
    (repo_path / "profiles").mkdir()
    (files / "zshrc.base").write_text("# base zshrc\nexport PATH=$HOME/.local/bin:$PATH\n")
    (files / "aliases.zsh").write_text("alias ll='ls -la'\n")
    return repo_path


@pytest.fixture
def base_profile(repo) -> profiles.ResolvedProfile:
    return profiles.ResolvedProfile(
        name="base",
        zshrc_files=[repo / "files" / "zshrc.base"],
        tools=[],
        env={},
        dotfiles=[],
    )


# — expected_content ——————————————————————————————————————————————————————————


def test_expected_content_starts_with_header(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    assert content.startswith(zshrc.PAULDOT_HEADER)


def test_expected_content_includes_zshrc_file_content(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    assert "# base zshrc" in content
    assert "export PATH=$HOME/.local/bin:$PATH" in content


def test_expected_content_includes_aliases(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    assert "alias ll='ls -la'" in content


def test_expected_content_no_source_lines(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    source_commands = [line for line in content.splitlines() if line.startswith("source ")]
    assert source_commands == [], f"unexpected source commands: {source_commands}"


def test_expected_content_omits_aliases_if_missing(repo, base_profile):
    (repo / "files" / "aliases.zsh").unlink()
    content = zshrc.expected_content(repo, base_profile)
    assert "aliases.zsh" not in content
    assert "alias" not in content


def test_expected_content_omits_env_section_if_no_env(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    assert "# Environment — set by active profile" not in content


def test_expected_content_exports_env_vars(repo):
    profile = profiles.ResolvedProfile(
        name="work",
        zshrc_files=[repo / "files" / "zshrc.base"],
        tools=[],
        env={"EDITOR": "zed --wait", "WORK_MODE": "true"},
        dotfiles=[],
    )
    content = zshrc.expected_content(repo, profile)
    assert 'export EDITOR="zed --wait"' in content
    assert 'export WORK_MODE="true"' in content


def test_expected_content_exports_env_vars_sorted(repo):
    profile = profiles.ResolvedProfile(
        name="base",
        zshrc_files=[],
        tools=[],
        env={"ZZZ": "last", "AAA": "first"},
        dotfiles=[],
    )
    content = zshrc.expected_content(repo, profile)
    aaa_pos = content.index("AAA")
    zzz_pos = content.index("ZZZ")
    assert aaa_pos < zzz_pos


def test_expected_content_includes_profile_aliases(repo, base_profile):
    (repo / "files" / "aliases.base.zsh").write_text("alias pb='pauldot'\n")
    content = zshrc.expected_content(repo, base_profile)
    assert "alias pb='pauldot'" in content


def test_expected_content_omits_profile_aliases_if_missing(repo, base_profile):
    content = zshrc.expected_content(repo, base_profile)
    assert "aliases.base.zsh" not in content


def test_expected_content_parent_before_child(repo):
    (repo / "files" / "zshrc.work").write_text("# work zshrc\n")
    profile = profiles.ResolvedProfile(
        name="work",
        zshrc_files=[repo / "files" / "zshrc.base", repo / "files" / "zshrc.work"],
        tools=[],
        env={},
        dotfiles=[],
    )
    content = zshrc.expected_content(repo, profile)
    base_pos = content.index("# base zshrc")
    work_pos = content.index("# work zshrc")
    assert base_pos < work_pos


def test_expected_content_is_deterministic(repo, base_profile):
    assert zshrc.expected_content(repo, base_profile) == zshrc.expected_content(repo, base_profile)


# — apply_zshrc ———————————————————————————————————————————————————————————————


def test_fresh_install_creates_plain_file(fake_home, repo, base_profile):
    result = zshrc.apply_zshrc(fake_home, repo, base_profile)
    zshrc_path = fake_home / ".zshrc"
    assert result.action == "created"
    assert zshrc_path.is_file()
    assert not zshrc_path.is_symlink()
    assert zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER)
    assert result.backup is None


def test_pauldot_owned_same_content_is_noop(fake_home, repo, base_profile):
    expected = zshrc.expected_content(repo, base_profile)
    (fake_home / ".zshrc").write_text(expected)
    result = zshrc.apply_zshrc(fake_home, repo, base_profile)
    assert result.action == "no_op"
    assert result.backup is None


def test_pauldot_owned_stale_content_is_written(fake_home, repo, base_profile):
    (fake_home / ".zshrc").write_text(zshrc.PAULDOT_HEADER + "\n# old content\n")
    result = zshrc.apply_zshrc(fake_home, repo, base_profile)
    assert result.action == "written"
    assert result.backup is None
    assert "# old content" not in (fake_home / ".zshrc").read_text()
    assert (fake_home / ".zshrc").read_text().startswith(zshrc.PAULDOT_HEADER)


def test_non_pauldot_file_is_backed_up(fake_home, repo, base_profile):
    (fake_home / ".zshrc").write_text("# my old zshrc\n")
    result = zshrc.apply_zshrc(fake_home, repo, base_profile)
    assert result.action == "backup_replaced"
    assert result.backup is not None
    assert result.backup.read_text() == "# my old zshrc\n"
    assert (fake_home / ".zshrc").read_text().startswith(zshrc.PAULDOT_HEADER)


def test_symlink_migration_removes_symlink_writes_plain_file(fake_home, repo, base_profile):
    target = fake_home / "some_generated_file"
    target.write_text("# old generated\n")
    (fake_home / ".zshrc").symlink_to(target)
    result = zshrc.apply_zshrc(fake_home, repo, base_profile)
    zshrc_path = fake_home / ".zshrc"
    assert result.action == "created"
    assert not zshrc_path.is_symlink()
    assert zshrc_path.is_file()
    assert zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER)


def test_dry_run_does_not_modify_filesystem(fake_home, repo, base_profile):
    (fake_home / ".zshrc").write_text("# untouched\n")
    result = zshrc.apply_zshrc(fake_home, repo, base_profile, dry_run=True)
    assert result.action == "backup_replaced"
    assert (fake_home / ".zshrc").read_text() == "# untouched\n"
    assert result.backup is not None
    assert not result.backup.exists()


def test_dry_run_no_file_does_not_create(fake_home, repo, base_profile):
    result = zshrc.apply_zshrc(fake_home, repo, base_profile, dry_run=True)
    assert result.action == "created"
    assert not (fake_home / ".zshrc").exists()


def test_dry_run_symlink_not_removed(fake_home, repo, base_profile):
    target = fake_home / "generated"
    target.write_text("# old\n")
    (fake_home / ".zshrc").symlink_to(target)
    result = zshrc.apply_zshrc(fake_home, repo, base_profile, dry_run=True)
    assert result.action == "created"
    assert (fake_home / ".zshrc").is_symlink()
