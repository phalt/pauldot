"""Tests for absorb.py — absorbing external zshrc modifications into source files."""

import pathlib

import pytest

from pauldot import absorb, profiles, state, zshrc


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    r = tmp_path / "dotfiles"
    (r / "files").mkdir(parents=True)
    (r / "files" / "aliases.zsh").write_text("# Aliases\n")
    (r / "files" / "zshrc.base").write_text("# Base zsh config\n")
    (r / "profiles").mkdir()
    (r / "profiles" / "personal.toml").write_text('zshrc = "files/zshrc.personal"\n')
    (r / "files" / "zshrc.personal").write_text("# Personal config\n")
    return r


@pytest.fixture
def profile(repo) -> profiles.ResolvedProfile:
    return profiles.resolve(repo, "personal")


@pytest.fixture
def fake_home_with_state(fake_home, repo) -> pathlib.Path:
    """fake_home with state.toml written, repo symlinked as .pauldot."""
    state.save_state(state.State(active_profile="personal", repo_url="git@github.com:test/dotfiles"))
    (fake_home / ".pauldot").symlink_to(repo)
    return fake_home


def _write_generated(repo: pathlib.Path, profile: profiles.ResolvedProfile, extra: str = "") -> pathlib.Path:
    """Write a .zshrc.generated file, optionally appending extra lines."""
    path = repo / zshrc.GENERATED_ZSHRC_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(zshrc.expected_content(repo, profile) + extra)
    return path


def test_nothing_to_absorb(fake_home_with_state, repo, profile):
    _write_generated(repo, profile)
    result = absorb.absorb(fake_home_with_state, repo)
    assert result.lines == []
    assert result.target is None


def test_absorbs_appended_lines(fake_home_with_state, repo, profile):
    extra = '\nexport NVM_DIR="$HOME/.nvm"\n[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"\n'
    _write_generated(repo, profile, extra)

    result = absorb.absorb(fake_home_with_state, repo)

    assert len(result.lines) == 2
    assert 'export NVM_DIR="$HOME/.nvm"' in result.lines
    assert '[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"' in result.lines

    base_content = (repo / "files" / "zshrc.base").read_text()
    assert 'export NVM_DIR' in base_content
    assert "# Absorbed by pauldot absorb" in base_content


def test_dry_run_does_not_write(fake_home_with_state, repo, profile):
    extra = '\nexport NVM_DIR="$HOME/.nvm"\n'
    _write_generated(repo, profile, extra)
    original = (repo / "files" / "zshrc.base").read_text()

    result = absorb.absorb(fake_home_with_state, repo, dry_run=True)

    assert result.lines == ['export NVM_DIR="$HOME/.nvm"']
    assert result.dry_run is True
    assert result.target is None
    assert (repo / "files" / "zshrc.base").read_text() == original


def test_absorbs_into_custom_target(fake_home_with_state, repo, profile):
    extra = '\nexport PYENV_ROOT="$HOME/.pyenv"\n'
    _write_generated(repo, profile, extra)

    result = absorb.absorb(fake_home_with_state, repo, target_name="zshrc.personal")

    assert result.target == repo / "files" / "zshrc.personal"
    assert 'export PYENV_ROOT' in (repo / "files" / "zshrc.personal").read_text()


def test_raises_if_generated_missing(fake_home_with_state, repo):
    with pytest.raises(FileNotFoundError, match="pauldot apply"):
        absorb.absorb(fake_home_with_state, repo)


def test_extra_lines_prefix_match():
    expected = "line1\nline2\nline3\n"
    actual = "line1\nline2\nline3\nextra1\nextra2\n"
    result = absorb._extra_lines(actual, expected)
    assert result == ["extra1", "extra2"]


def test_extra_lines_fallback_set_diff():
    expected = "line1\nline2\n"
    actual = "line1\nINSERTED\nline2\n"
    result = absorb._extra_lines(actual, expected)
    assert result == ["INSERTED"]


def test_extra_lines_blank_lines_excluded():
    expected = "line1\n"
    actual = "line1\n\n   \nextra\n"
    result = absorb._extra_lines(actual, expected)
    assert result == ["extra"]
