"""Sync pipeline: pull → detect per-file changes → update sync state → commit → push.

Call sync.run(home) to execute the full pipeline. Results are returned as a
SyncResult; errors that require user action are represented in blocked_by_state
or sync_results rather than raised as exceptions. Infrastructure failures
(git errors, missing config) are raised as RuntimeError.
"""

import pathlib

import pydantic

from pauldot import config, dotfiles, git, profiles, state


class SyncResult(pydantic.BaseModel):
    sync_results: list[dotfiles.DotfileSyncResult] = []
    committed: bool = False
    pushed: bool = False
    # Non-empty when sync was blocked by unresolved items from a previous run.
    # When this is set, no pull or push was attempted — git state is unchanged.
    blocked_by_state: list[dotfiles.DotfileSyncResult] = []


def run(home: pathlib.Path) -> SyncResult:
    """Execute the full sync pipeline for the machine at *home*.

    Flow:
      1. Check state for unresolved items from a previous sync.
         If any are still unresolved (live != repo), return blocked immediately
         without touching git.
      2. Commit any uncommitted changes in the dotfiles repo (requires auto_commit).
      3. Pull (--rebase).
      4. Smart-detect per-file what changed on each side during the pull.
      5. If attention is needed (remote_updated / conflict), save to state
         and return without pushing.
      6. Commit any synced live→repo copies, push, clear sync fields in state.
    """
    repo_path = home / ".pauldot"

    try:
        s = state.load_state()
        profile = profiles.resolve(repo_path, s.active_profile)
    except FileNotFoundError as e:
        raise RuntimeError(str(e)) from None

    # Step 1 — pre-flight: check for unresolved items from a previous sync run.
    if s.has_attention:
        still_blocked = _check_existing_attention(s, profile.dotfiles, home, repo_path)
        if still_blocked:
            state.save_state(
                s.model_copy(
                    update={
                        "remote_updated": [r.path for r in still_blocked if r.action == "remote_updated"],
                        "conflict": [r.path for r in still_blocked if r.action == "conflict"],
                    }
                )
            )
            return SyncResult(blocked_by_state=still_blocked)
        # All previously flagged items are now resolved — clear and proceed.
        state.save_state(s.model_copy(update={"remote_updated": [], "conflict": []}))

    # Step 2 — commit pre-pull dirty changes so git pull --rebase doesn't refuse.
    if git.has_uncommitted_changes(repo_path):
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, "pauldot: commit local changes before sync")
        else:
            raise RuntimeError(
                "Uncommitted changes in your dotfiles repo.\n"
                "Commit or stash them before syncing, or set auto_commit = true in pauldot.toml."
            )

    # Step 3 — pull.
    before_sha = git.head_sha(repo_path)
    git.pull_rebase(repo_path)
    after_sha = git.head_sha(repo_path)

    # Step 4 — smart per-file sync detection.
    sync_results: list[dotfiles.DotfileSyncResult] = []
    if profile.dotfiles:
        sync_results = dotfiles.smart_sync_dotfiles(profile.dotfiles, home, repo_path, before_sha, after_sha)

    # Step 5 — handle attention items.
    needs_attention = [r for r in sync_results if r.action in ("remote_updated", "conflict")]
    if needs_attention:
        state.save_state(
            s.model_copy(
                update={
                    "remote_updated": [r.path for r in needs_attention if r.action == "remote_updated"],
                    "conflict": [r.path for r in needs_attention if r.action == "conflict"],
                }
            )
        )
        return SyncResult(sync_results=sync_results)

    # Step 6 — commit any live→repo copies that smart sync wrote, then push.
    committed = False
    if git.has_uncommitted_changes(repo_path):
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, "pauldot: sync dotfiles")
            committed = True
        else:
            raise RuntimeError(
                "Uncommitted changes in your dotfiles repo after sync.\n"
                "Commit or stash them, or set auto_commit = true in pauldot.toml."
            )

    pushed = False
    if git.has_unpushed_commits(repo_path):
        git.push(repo_path)
        pushed = True

    state.save_state(s.model_copy(update={"remote_updated": [], "conflict": []}))
    return SyncResult(sync_results=sync_results, committed=committed, pushed=pushed)


def _check_existing_attention(
    s: state.State,
    tracked_dotfiles: list[str],
    home: pathlib.Path,
    repo_path: pathlib.Path,
) -> list[dotfiles.DotfileSyncResult]:
    """Re-check previously flagged paths against the current filesystem.

    A path is considered resolved when live == repo on disk. Paths that are no
    longer in the active profile are silently dropped (treated as resolved).
    Returns the subset that is still unresolved.
    """
    unresolved: list[dotfiles.DotfileSyncResult] = []
    for path, action in s.all_pending():
        if path not in tracked_dotfiles:
            continue
        live = home / path
        repo_file = dotfiles.repo_path_for(path, repo_path)
        if not live.exists() or not repo_file.exists():
            unresolved.append(dotfiles.DotfileSyncResult(path=path, action=action))
            continue
        if live.read_bytes() != repo_file.read_bytes():
            unresolved.append(dotfiles.DotfileSyncResult(path=path, action=action))
    return unresolved
