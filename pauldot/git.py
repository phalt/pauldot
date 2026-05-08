"""Subprocess wrappers for git."""

import pathlib
import subprocess


def clone(url: str, dest: pathlib.Path) -> None:
    """Clone a git repo to dest. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed:\n{result.stderr.strip()}")


def commit(repo_path: pathlib.Path, message: str) -> None:
    """Stage all changes and create a commit. Raises RuntimeError on failure."""
    stage = subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, text=True)
    if stage.returncode != 0:
        raise RuntimeError(f"git add failed:\n{stage.stderr.strip()}")

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # "nothing to commit" is not an error.
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            return
        raise RuntimeError(f"git commit failed:\n{result.stderr.strip()}")


def has_uncommitted_changes(repo_path: pathlib.Path) -> bool:
    """Return True if there are staged or unstaged changes in the working tree."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def has_unpushed_commits(repo_path: pathlib.Path) -> bool:
    """Return True if there are local commits not yet on the remote."""
    result = subprocess.run(
        ["git", "rev-list", "--count", "@{u}..HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # No upstream tracking branch — treat as nothing to push.
        return False
    return result.stdout.strip() != "0"


def pull_rebase(repo_path: pathlib.Path) -> str:
    """git pull --rebase. Returns stdout. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["git", "pull", "--rebase"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git pull --rebase failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def push(repo_path: pathlib.Path) -> str:
    """git push. Returns stdout. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["git", "push"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git push failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def head_sha(repo_path: pathlib.Path) -> str:
    """Return the current HEAD commit SHA, or empty string if not in a git repo."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def show_file(repo_path: pathlib.Path, sha: str, path: str) -> bytes | None:
    """Return file content at the given commit SHA, or None if the path is not in the tree."""
    if not sha:
        return None
    result = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout
