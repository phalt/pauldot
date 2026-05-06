"""Tests for git.py — subprocess wrappers."""

import pathlib
import subprocess

import pytest

from pauldot import git


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    """A real local git repo with an initial commit."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_commit_stages_and_commits(repo):
    (repo / "new.txt").write_text("new\n")
    git.commit(repo, "add new.txt")

    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True)
    assert "add new.txt" in log.stdout


def test_commit_nothing_to_commit_is_noop(repo):
    """commit() with no changes does not raise."""
    git.commit(repo, "nothing here")


def test_has_unpushed_commits_no_upstream(repo):
    """No upstream tracking branch → False, not an error."""
    assert git.has_unpushed_commits(repo) is False


def test_has_unpushed_commits_with_upstream(tmp_path):
    """Repo with commits ahead of remote returns True."""
    # Create a non-bare origin with an initial commit so clones have an upstream.
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "receive.denyCurrentBranch", "ignore"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    (origin / "init.txt").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=origin, check=True, capture_output=True)

    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(origin), str(local)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=local, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=local, check=True, capture_output=True)

    (local / "x.txt").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "ahead"], cwd=local, check=True, capture_output=True)

    assert git.has_unpushed_commits(local) is True
