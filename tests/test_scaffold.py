"""Tests for scaffold.py — dotfiles repo generation from templates."""

import pathlib

import pytest

from pauldot import scaffold


def test_generate_creates_expected_files(tmp_path):
    dest = tmp_path / "dotfiles"
    created = scaffold.generate(dest)

    relative = {p.relative_to(dest) for p in created}

    assert pathlib.Path("pauldot.toml") in relative
    assert pathlib.Path("bootstrap.sh") in relative
    assert pathlib.Path("profiles/base.toml") in relative
    assert pathlib.Path("profiles/personal.toml") in relative
    assert pathlib.Path("files/aliases.zsh") in relative
    assert pathlib.Path("files/zshrc.base") in relative
    assert pathlib.Path("tools/tools.toml") in relative


def test_generate_returns_only_files(tmp_path):
    dest = tmp_path / "dotfiles"
    created = scaffold.generate(dest)
    assert all(p.is_file() for p in created)


def test_generate_raises_if_dest_non_empty(tmp_path):
    dest = tmp_path / "dotfiles"
    dest.mkdir()
    (dest / "something.txt").write_text("oops")

    with pytest.raises(FileExistsError, match="not empty"):
        scaffold.generate(dest)


def test_generate_succeeds_if_dest_missing(tmp_path):
    dest = tmp_path / "new-dotfiles"
    assert not dest.exists()
    scaffold.generate(dest)
    assert dest.is_dir()


def test_generate_succeeds_if_dest_empty_dir(tmp_path):
    dest = tmp_path / "dotfiles"
    dest.mkdir()
    scaffold.generate(dest)
    assert (dest / "pauldot.toml").exists()


def test_generate_succeeds_if_dest_has_only_dotgit(tmp_path):
    """A freshly-cloned empty git repo (just .git/) should be treated as empty."""
    dest = tmp_path / "dotfiles"
    dest.mkdir()
    (dest / ".git").mkdir()
    scaffold.generate(dest)
    assert (dest / "pauldot.toml").exists()
