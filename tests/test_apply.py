"""Tests for apply.run() — the full reconciliation pipeline."""

import pathlib

import pytest

from pauldot import apply, state, zshrc

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
    s = state.State(active_profile="base", repo_url="git@github.com:test/dotfiles")
    state.save_state(s)
    return s


# — apply.run() ————————————————————————————————————————————————————————————————


def test_apply_run_creates_plain_file(fake_home, repo, saved_state):
    result = apply.run(fake_home)
    zshrc_path = fake_home / ".zshrc"
    assert result.zshrc.action == "created"
    assert zshrc_path.is_file()
    assert not zshrc_path.is_symlink()
    assert zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER)


def test_apply_run_content_includes_source_files(fake_home, repo, saved_state):
    apply.run(fake_home)
    content = (fake_home / ".zshrc").read_text()
    assert "# base" in content
    assert "# aliases" in content


def test_apply_run_idempotent(fake_home, repo, saved_state):
    apply.run(fake_home)
    first_content = (fake_home / ".zshrc").read_text()
    result2 = apply.run(fake_home)
    assert result2.zshrc.action == "no_op"
    assert (fake_home / ".zshrc").read_text() == first_content


def test_apply_run_dry_run_no_file_created(fake_home, repo, saved_state):
    result = apply.run(fake_home, dry_run=True)
    assert result.zshrc.action == "created"
    assert not (fake_home / ".zshrc").exists()


def test_apply_run_dry_run_skips_tools(fake_home, repo, saved_state):
    (repo / "tools").mkdir()
    (repo / "tools" / "tools.toml").write_text(
        '[[tool]]\nname = "t"\ncheck = "false"\n\n[tool.install]\nlinux = "true"\n'
    )
    (repo / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\ntools = ["t"]\n')
    result = apply.run(fake_home, dry_run=True)
    assert result.tools == []


def test_apply_run_reconciles_tools(fake_home, repo, saved_state):
    (repo / "tools").mkdir()
    (repo / "tools" / "tools.toml").write_text('[[tool]]\nname = "t"\ncheck = "true"\n')
    (repo / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\ntools = ["t"]\n')
    result = apply.run(fake_home)
    assert len(result.tools) == 1
    assert result.tools[0].name == "t"
    assert result.tools[0].action == "already_installed"


def test_apply_run_migrates_symlink(fake_home, repo, saved_state):
    """If ~/.zshrc is a symlink (old model), apply removes it and writes a plain file."""
    generated = repo / "files" / ".zshrc.generated"
    generated.write_text("# old generated\n")
    (fake_home / ".zshrc").symlink_to(generated)
    result = apply.run(fake_home)
    zshrc_path = fake_home / ".zshrc"
    assert result.zshrc.action == "created"
    assert not zshrc_path.is_symlink()
    assert zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER)


def test_apply_run_no_state_raises(fake_home, repo):
    with pytest.raises(FileNotFoundError, match="pauldot init"):
        apply.run(fake_home)
