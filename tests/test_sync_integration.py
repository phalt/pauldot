"""Integration tests for the full pauldot sync pipeline.

These tests drive all five sync scenarios end-to-end, using a real local
git origin+clone pair so no git operations are mocked. The sync_state.toml
file is the key invariant: the tests assert on it directly to verify that
state is saved, re-read, and cleared correctly across multiple sync runs.

Scenarios covered:
  1. no_change        — live matches repo, nothing to do
  2. synced           — only local changed; copied to repo and pushed
  3. remote_updated   — first run ejects and saves sync_state
  4. remote_updated   — second run without resolving STILL ejects (the regression guard)
  5. remote_updated   — resolved via apply --overwrite; next sync proceeds cleanly
  6. conflict         — first run ejects and saves sync_state
  7. conflict         — second run without resolving STILL ejects
  8. conflict         — resolved via apply --overwrite; next sync proceeds cleanly
  9. conflict         — resolved manually (user edits both sides); next sync proceeds cleanly
"""

import pathlib
import subprocess

import pytest

from pauldot import apply as pauldot_apply
from pauldot import state, sync

# ——————————————————————————————————————————————————————————————————————————————
# Helpers
# ——————————————————————————————————————————————————————————————————————————————


def _git(args: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


def _commit_all(repo: pathlib.Path, msg: str) -> None:
    _git(["add", "-A"], repo)
    _git(["commit", "-m", msg], repo)


def _push_remote_change(origin: pathlib.Path, content: str) -> None:
    """Simulate Machine B pushing a dotfile change directly to origin."""
    (origin / "files" / "home" / ".gitconfig").write_text(content)
    _commit_all(origin, "remote: update .gitconfig")


# ——————————————————————————————————————————————————————————————————————————————
# Fixtures
# ——————————————————————————————————————————————————————————————————————————————

_ORIGIN_GITCONFIG = "[user]\n  name = Origin\n"
_LOCAL_EDIT = "[user]\n  name = LocalEdit\n"
_REMOTE_UPDATE = "[user]\n  name = RemoteUpdate\n"
_MERGED = "[user]\n  name = Merged\n"


@pytest.fixture
def origin(tmp_path) -> pathlib.Path:
    """A non-bare git repo acting as the remote origin, pre-populated with a
    minimal pauldot structure and an initial .gitconfig dotfile."""
    o = tmp_path / "origin"
    o.mkdir()
    _git(["init"], o)
    _git(["config", "user.email", "t@t.com"], o)
    _git(["config", "user.name", "T"], o)
    # Allow pushes to a non-bare repo (the pushed working tree won't update,
    # but git history is updated — sufficient for our tests).
    _git(["config", "receive.denyCurrentBranch", "ignore"], o)
    (o / "files" / "home").mkdir(parents=True)
    (o / "profiles").mkdir()
    (o / "pauldot.toml").write_text('[core]\ndefault_profile = "base"\n\n[git]\nauto_commit = true\n')
    (o / "profiles" / "base.toml").write_text('zshrc = "files/zshrc.base"\ndotfiles = [".gitconfig"]\n')
    (o / "files" / "zshrc.base").write_text("# base\n")
    (o / "files" / "home" / ".gitconfig").write_text(_ORIGIN_GITCONFIG)
    _commit_all(o, "init")
    return o


@pytest.fixture
def setup(fake_home, origin) -> tuple[pathlib.Path, pathlib.Path]:
    """Clone origin into fake_home/.pauldot and write a valid state.toml.

    Returns (home, repo_path).
    """
    home = fake_home
    repo_path = home / ".pauldot"
    subprocess.run(
        ["git", "clone", str(origin), str(repo_path)],
        check=True,
        capture_output=True,
    )
    _git(["config", "user.email", "t@t.com"], repo_path)
    _git(["config", "user.name", "T"], repo_path)
    state.save_state(state.State(active_profile="base", repo_url=str(origin)))
    return home, repo_path


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 1: no_change
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_no_change(setup):
    """Live file matches repo; sync is a no-op with nothing committed or pushed."""
    home, repo = setup
    (home / ".gitconfig").write_text(_ORIGIN_GITCONFIG)

    result = sync.run(home)

    assert result.blocked_by_state == []
    assert len(result.sync_results) == 1
    assert result.sync_results[0].action == "no_change"
    assert result.committed is False
    assert result.pushed is False
    assert not state.load_state().has_attention


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 2: synced — only local changed
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_local_changed(setup):
    """User edited live file; sync copies it to repo, commits, and pushes."""
    home, repo = setup
    (home / ".gitconfig").write_text(_LOCAL_EDIT)

    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "synced"
    assert result.committed is True
    assert result.pushed is True
    assert (repo / "files" / "home" / ".gitconfig").read_text() == _LOCAL_EDIT
    assert not state.load_state().has_attention


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 3: remote_updated — first run
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_remote_updated_first_run_ejects(setup, origin):
    """Remote changed, live at old version → ejects and saves sync_state."""
    home, repo = setup
    (home / ".gitconfig").write_text(_ORIGIN_GITCONFIG)
    _push_remote_change(origin, _REMOTE_UPDATE)

    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "remote_updated"
    assert result.committed is False
    assert result.pushed is False
    # sync_state must be persisted so the next run also ejects
    ss = state.load_state()
    assert ".gitconfig" in ss.remote_updated
    # live file must not be touched
    assert (home / ".gitconfig").read_text() == _ORIGIN_GITCONFIG


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 4: remote_updated — second run without resolving MUST still eject
# This is the core regression guard: without sync_state the second run would
# silently overwrite the remote change with the stale live file.
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_remote_updated_second_run_still_ejects(setup, origin):
    """Running sync again without resolving remote_updated must always eject."""
    home, repo = setup
    (home / ".gitconfig").write_text(_ORIGIN_GITCONFIG)
    _push_remote_change(origin, _REMOTE_UPDATE)

    # First sync — ejects and saves state
    result1 = sync.run(home)
    assert result1.sync_results[0].action == "remote_updated"

    # Second sync WITHOUT running apply --overwrite
    result2 = sync.run(home)

    assert result2.blocked_by_state != [], "second sync must be blocked, not proceed"
    assert result2.blocked_by_state[0].path == ".gitconfig"
    assert result2.blocked_by_state[0].action == "remote_updated"
    # Neither live nor repo must be touched
    assert (home / ".gitconfig").read_text() == _ORIGIN_GITCONFIG
    assert (repo / "files" / "home" / ".gitconfig").read_text() == _REMOTE_UPDATE


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 5: remote_updated — resolved via apply --overwrite
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_remote_updated_resolved_by_apply_overwrite(setup, origin):
    """After apply --overwrite pulls down remote version, sync proceeds cleanly."""
    home, repo = setup
    (home / ".gitconfig").write_text(_ORIGIN_GITCONFIG)
    _push_remote_change(origin, _REMOTE_UPDATE)

    # First sync — ejects
    sync.run(home)

    # User resolves by accepting the remote version
    pauldot_apply.run(home, overwrite=True)

    # Sync should now proceed without being blocked
    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "no_change"
    assert not state.load_state().has_attention
    assert (home / ".gitconfig").read_text() == _REMOTE_UPDATE


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 6: conflict — first run
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_conflict_first_run_ejects(setup, origin):
    """Both local and remote changed → conflict; ejects and saves sync_state."""
    home, repo = setup
    (home / ".gitconfig").write_text(_LOCAL_EDIT)
    _push_remote_change(origin, _REMOTE_UPDATE)

    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "conflict"
    assert result.committed is False
    assert result.pushed is False
    ss = state.load_state()
    assert ".gitconfig" in ss.conflict
    # Neither side touched
    assert (home / ".gitconfig").read_text() == _LOCAL_EDIT
    assert (repo / "files" / "home" / ".gitconfig").read_text() == _REMOTE_UPDATE


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 7: conflict — second run without resolving MUST still eject
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_conflict_second_run_still_ejects(setup, origin):
    """Running sync again with an unresolved conflict must always eject."""
    home, repo = setup
    (home / ".gitconfig").write_text(_LOCAL_EDIT)
    _push_remote_change(origin, _REMOTE_UPDATE)

    # First sync — conflict
    sync.run(home)

    # Second sync WITHOUT resolving
    result2 = sync.run(home)

    assert result2.blocked_by_state != [], "second sync must be blocked, not proceed"
    assert result2.blocked_by_state[0].path == ".gitconfig"
    assert result2.blocked_by_state[0].action == "conflict"
    # Files must be unchanged
    assert (home / ".gitconfig").read_text() == _LOCAL_EDIT
    assert (repo / "files" / "home" / ".gitconfig").read_text() == _REMOTE_UPDATE


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 8: conflict — resolved via apply --overwrite (accept remote version)
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_conflict_resolved_by_apply_overwrite(setup, origin):
    """Accepting remote version via apply --overwrite clears conflict; sync proceeds."""
    home, repo = setup
    (home / ".gitconfig").write_text(_LOCAL_EDIT)
    _push_remote_change(origin, _REMOTE_UPDATE)

    # Conflict detected and saved
    sync.run(home)

    # User accepts remote version
    pauldot_apply.run(home, overwrite=True)

    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "no_change"
    assert not state.load_state().has_attention
    assert (home / ".gitconfig").read_text() == _REMOTE_UPDATE


# ——————————————————————————————————————————————————————————————————————————————
# Scenario 9: conflict — resolved manually (user edits both sides to merged)
# ——————————————————————————————————————————————————————————————————————————————


def test_sync_conflict_resolved_manually(setup, origin):
    """User manually merges: edits live and copies to repo. Next sync clears and proceeds."""
    home, repo = setup
    (home / ".gitconfig").write_text(_LOCAL_EDIT)
    _push_remote_change(origin, _REMOTE_UPDATE)

    # Conflict detected
    sync.run(home)

    # User manually edits live to a merged version and copies it to the repo
    (home / ".gitconfig").write_text(_MERGED)
    (repo / "files" / "home" / ".gitconfig").write_text(_MERGED)

    # Sync detects live == repo → conflict resolved; commits merged version and pushes
    result = sync.run(home)

    assert result.blocked_by_state == []
    assert result.sync_results[0].action == "no_change"
    assert not state.load_state().has_attention
    assert (home / ".gitconfig").read_text() == _MERGED
