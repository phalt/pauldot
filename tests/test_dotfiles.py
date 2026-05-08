"""Tests for dotfiles.py — copy-on-sync dotfile tracking."""

import pathlib
import subprocess as _subprocess

import pytest

from pauldot import dotfiles


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    repo_path = tmp_path / "dotfiles"
    (repo_path / "files" / "home").mkdir(parents=True)
    return repo_path


@pytest.fixture
def home(tmp_path) -> pathlib.Path:
    return tmp_path / "home"


# — repo_path_for() ——————————————————————————————————————————————————————————


def test_repo_path_for_flat(repo):
    result = dotfiles.repo_path_for(".gitconfig", repo)
    assert result == repo / "files" / "home" / ".gitconfig"


def test_repo_path_for_nested(repo):
    result = dotfiles.repo_path_for(".config/starship.toml", repo)
    assert result == repo / "files" / "home" / ".config" / "starship.toml"


# — status() —————————————————————————————————————————————————————————————————


def test_status_in_sync(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n  name = Paul\n")
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.status([".gitconfig"], home, repo)
    assert results[0].state == "in_sync"


def test_status_drift(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n  name = Paul\n")
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Someone Else\n")
    results = dotfiles.status([".gitconfig"], home, repo)
    assert results[0].state == "drift"


def test_status_not_in_repo(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.status([".gitconfig"], home, repo)
    assert results[0].state == "not_in_repo"


def test_status_not_on_disk(home, repo):
    home.mkdir()
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.status([".gitconfig"], home, repo)
    assert results[0].state == "not_on_disk"


def test_status_empty_list(home, repo):
    home.mkdir()
    assert dotfiles.status([], home, repo) == []


def test_status_nested_path(home, repo):
    (home / ".config").mkdir(parents=True)
    (home / ".config" / "starship.toml").write_text("# starship\n")
    (repo / "files" / "home" / ".config").mkdir(parents=True)
    (repo / "files" / "home" / ".config" / "starship.toml").write_text("# starship\n")
    results = dotfiles.status([".config/starship.toml"], home, repo)
    assert results[0].state == "in_sync"


# — apply_dotfiles() ——————————————————————————————————————————————————————————


def test_apply_copies_missing_live(home, repo):
    home.mkdir()
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo)
    assert results[0].action == "copied"
    assert (home / ".gitconfig").exists()
    assert (home / ".gitconfig").read_text() == "[user]\n  name = Paul\n"


def test_apply_already_present(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n  name = Paul\n")
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo)
    assert results[0].action == "already_present"


def test_apply_already_present_does_not_overwrite(home, repo):
    """apply never overwrites the live file — live is source of truth."""
    home.mkdir()
    (home / ".gitconfig").write_text("local content")
    (repo / "files" / "home" / ".gitconfig").write_text("repo content")
    dotfiles.apply_dotfiles([".gitconfig"], home, repo)
    assert (home / ".gitconfig").read_text() == "local content"


def test_apply_missing_source(home, repo):
    home.mkdir()
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo)
    assert results[0].action == "missing_source"
    assert not (home / ".gitconfig").exists()


def test_apply_dry_run_no_copy(home, repo):
    home.mkdir()
    (repo / "files" / "home" / ".gitconfig").write_text("[user]\n  name = Paul\n")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo, dry_run=True)
    assert results[0].action == "copied"
    assert not (home / ".gitconfig").exists()


def test_apply_creates_parent_dirs(home, repo):
    home.mkdir()
    (repo / "files" / "home" / ".config").mkdir(parents=True)
    (repo / "files" / "home" / ".config" / "starship.toml").write_text("# starship\n")
    results = dotfiles.apply_dotfiles([".config/starship.toml"], home, repo)
    assert results[0].action == "copied"
    assert (home / ".config" / "starship.toml").exists()


def test_apply_empty_list(home, repo):
    home.mkdir()
    assert dotfiles.apply_dotfiles([], home, repo) == []


# — apply_dotfiles() with overwrite=True ——————————————————————————————————————


def test_apply_overwrite_replaces_differing_live(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("old content")
    (repo / "files" / "home" / ".gitconfig").write_text("new content from repo")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo, overwrite=True)
    assert results[0].action == "overwritten"
    assert results[0].backup is not None
    assert results[0].backup.exists()
    assert results[0].backup.read_text() == "old content"
    assert (home / ".gitconfig").read_text() == "new content from repo"


def test_apply_overwrite_noop_when_identical(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("same content")
    (repo / "files" / "home" / ".gitconfig").write_text("same content")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo, overwrite=True)
    assert results[0].action == "already_present"
    assert results[0].backup is None


def test_apply_overwrite_dry_run_no_changes(home, repo):
    home.mkdir()
    (home / ".gitconfig").write_text("old content")
    (repo / "files" / "home" / ".gitconfig").write_text("new content from repo")
    results = dotfiles.apply_dotfiles([".gitconfig"], home, repo, dry_run=True, overwrite=True)
    assert results[0].action == "overwritten"
    assert (home / ".gitconfig").read_text() == "old content"  # untouched


# — smart_sync_dotfiles() ——————————————————————————————————————————————————————


@pytest.fixture
def git_repo(tmp_path) -> pathlib.Path:
    """A real git repo with a files/home/ directory and git config."""
    r = tmp_path / "repo"
    r.mkdir()
    (r / "files" / "home").mkdir(parents=True)
    _subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
    _subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=r, check=True, capture_output=True)
    _subprocess.run(["git", "config", "user.name", "T"], cwd=r, check=True, capture_output=True)
    return r


def _commit(repo: pathlib.Path, msg: str) -> str:
    _subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    _subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    result = _subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def test_smart_sync_no_change(home, git_repo):
    """live == repo before and after pull — nothing to do."""
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    after_sha = before_sha  # no pull happened
    (home / ".gitconfig").write_text("v1")
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, after_sha)
    assert results[0].action == "no_change"


def test_smart_sync_local_changed(home, git_repo):
    """Only local changed — copy live → repo (synced)."""
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    after_sha = before_sha  # no remote change
    (home / ".gitconfig").write_text("v2 local edit")
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, after_sha)
    assert results[0].action == "synced"
    assert (git_repo / "files" / "home" / ".gitconfig").read_text() == "v2 local edit"


def test_smart_sync_remote_updated(home, git_repo):
    """Only remote changed — live still at old version."""
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    (git_repo / "files" / "home" / ".gitconfig").write_text("v2 from remote")
    after_sha = _commit(git_repo, "remote update")
    (home / ".gitconfig").write_text("v1")  # live still at v1
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, after_sha)
    assert results[0].action == "remote_updated"
    # live file must NOT be modified
    assert (home / ".gitconfig").read_text() == "v1"


def test_smart_sync_conflict(home, git_repo):
    """Both local and remote changed — conflict."""
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    (git_repo / "files" / "home" / ".gitconfig").write_text("v2 from remote")
    after_sha = _commit(git_repo, "remote update")
    (home / ".gitconfig").write_text("v3 local edit")  # different from both v1 and v2
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, after_sha)
    assert results[0].action == "conflict"
    # live file and repo must NOT be modified
    assert (home / ".gitconfig").read_text() == "v3 local edit"
    assert (git_repo / "files" / "home" / ".gitconfig").read_text() == "v2 from remote"


def test_smart_sync_missing_live(home, git_repo):
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, before_sha)
    assert results[0].action == "missing_live"


def test_smart_sync_dry_run_local_changed(home, git_repo):
    """dry_run=True: synced reported but repo not written."""
    home.mkdir()
    (git_repo / "files" / "home" / ".gitconfig").write_text("v1")
    before_sha = _commit(git_repo, "init")
    (home / ".gitconfig").write_text("v2 local")
    results = dotfiles.smart_sync_dotfiles([".gitconfig"], home, git_repo, before_sha, before_sha, dry_run=True)
    assert results[0].action == "synced"
    assert (git_repo / "files" / "home" / ".gitconfig").read_text() == "v1"  # untouched


def test_smart_sync_empty_list(home, git_repo):
    home.mkdir()
    assert dotfiles.smart_sync_dotfiles([], home, git_repo, "", "") == []
