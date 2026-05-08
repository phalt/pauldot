"""Dotfile tracking: copy-on-sync model. Remote is the source of truth for conflicts."""

import datetime
import pathlib
import shutil
import typing

import pydantic

from pauldot import git


class DotfileStatus(pydantic.BaseModel):
    path: str  # relative to $HOME
    state: typing.Literal["in_sync", "drift", "not_in_repo", "not_on_disk"]


class DotfileApplyResult(pydantic.BaseModel):
    path: str  # relative to $HOME
    action: typing.Literal["copied", "overwritten", "already_present", "missing_source"]
    backup: pathlib.Path | None = None


class DotfileSyncResult(pydantic.BaseModel):
    path: str  # relative to $HOME
    action: typing.Literal["no_change", "synced", "remote_updated", "conflict", "missing_live"]


def repo_path_for(home_rel: str, repo_path: pathlib.Path) -> pathlib.Path:
    """Return the repo storage path for a home-relative dotfile path."""
    return repo_path / "files" / "home" / home_rel


def status(dotfiles: list[str], home: pathlib.Path, repo_path: pathlib.Path) -> list[DotfileStatus]:
    """Compare live files against repo copies. Returns one status per dotfile."""
    results = []
    for home_rel in dotfiles:
        repo_file = repo_path_for(home_rel, repo_path)
        live = home / home_rel
        if not repo_file.exists():
            results.append(DotfileStatus(path=home_rel, state="not_in_repo"))
        elif not live.exists():
            results.append(DotfileStatus(path=home_rel, state="not_on_disk"))
        elif live.read_bytes() == repo_file.read_bytes():
            results.append(DotfileStatus(path=home_rel, state="in_sync"))
        else:
            results.append(DotfileStatus(path=home_rel, state="drift"))
    return results


def apply_dotfiles(
    dotfiles: list[str],
    home: pathlib.Path,
    repo_path: pathlib.Path,
    dry_run: bool = False,
    overwrite: bool = False,
) -> list[DotfileApplyResult]:
    """Bootstrap (or overwrite) live files from repo copies.

    Default (overwrite=False): only copies files that don't yet exist on disk.
    With overwrite=True: also updates existing live files that differ from the repo,
    creating a timestamped backup before replacing.
    """
    results = []
    for home_rel in dotfiles:
        repo_file = repo_path_for(home_rel, repo_path)
        live = home / home_rel
        if not repo_file.exists():
            results.append(DotfileApplyResult(path=home_rel, action="missing_source"))
            continue
        if live.exists():
            if live.read_bytes() == repo_file.read_bytes():
                results.append(DotfileApplyResult(path=home_rel, action="already_present"))
                continue
            if not overwrite:
                results.append(DotfileApplyResult(path=home_rel, action="already_present"))
                continue
            # overwrite=True and content differs — backup and replace
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup = live.with_name(f"{live.name}.bak.{ts}")
            if not dry_run:
                live.rename(backup)
                live.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, live)
            results.append(DotfileApplyResult(path=home_rel, action="overwritten", backup=backup))
            continue
        if not dry_run:
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_file, live)
        results.append(DotfileApplyResult(path=home_rel, action="copied"))
    return results


def smart_sync_dotfiles(
    dotfiles: list[str],
    home: pathlib.Path,
    repo_path: pathlib.Path,
    before_sha: str,
    after_sha: str,
    dry_run: bool = False,
) -> list[DotfileSyncResult]:
    """Sync dotfiles after a pull, with conflict detection.

    Compares live files against the repo state before and after the pull to
    determine which side changed:
      no_change      — live matches repo; nothing to do
      synced         — only local changed; copied live → repo (ready to push)
      remote_updated — only remote changed; user should run `pauldot apply --overwrite`
      conflict       — both sides changed; user must resolve manually
      missing_live   — live file does not exist; user should run `pauldot apply`
    """
    results = []
    for home_rel in dotfiles:
        repo_file = repo_path_for(home_rel, repo_path)
        live = home / home_rel
        git_path = f"files/home/{home_rel}"

        if not live.exists():
            results.append(DotfileSyncResult(path=home_rel, action="missing_live"))
            continue

        live_content = live.read_bytes()
        before_content = git.show_file(repo_path, before_sha, git_path)
        after_content = repo_file.read_bytes() if repo_file.exists() else None

        remote_changed = before_content != after_content
        local_changed = live_content != (before_content if before_content is not None else after_content)

        if not local_changed and not remote_changed:
            results.append(DotfileSyncResult(path=home_rel, action="no_change"))
        elif local_changed and not remote_changed:
            if not dry_run:
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live, repo_file)
            results.append(DotfileSyncResult(path=home_rel, action="synced"))
        elif remote_changed and not local_changed:
            results.append(DotfileSyncResult(path=home_rel, action="remote_updated"))
        else:
            results.append(DotfileSyncResult(path=home_rel, action="conflict"))

    return results
