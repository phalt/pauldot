"""The reconciliation engine: load state → resolve profile → write ~/.zshrc → reconcile tools."""

import pathlib

import pydantic
from rich import console as rich_console

from pauldot import config, dotfiles, profiles, shell, state, tools, zshrc


class ApplyResult(pydantic.BaseModel):
    zshrc: zshrc.ZshrcResult
    tools: list[tools.ToolResult]
    dotfiles: list[dotfiles.DotfileApplyResult]


def run(
    home: pathlib.Path,
    dry_run: bool = False,
    overwrite: bool = False,
    console: rich_console.Console | None = None,
) -> ApplyResult:
    """Run the apply pipeline.

    Loads state and config, resolves the active profile, writes ~/.zshrc as a plain file,
    and reconciles tools. In dry_run mode only the zshrc step runs (idempotent read + describe)
    and tools are skipped. With overwrite=True, existing live dotfiles that differ from the
    repo are backed up and replaced with the repo version.

    After applying dotfiles, any sync state entries that are now resolved (live == repo)
    are cleared from state.toml so that subsequent sync runs are not incorrectly blocked.
    """
    current_state = state.load_state()
    repo_path = home / ".pauldot"

    config.load_pauldot_config(repo_path)  # validates the repo
    profile = profiles.resolve(repo_path, current_state.active_profile)
    os_name = shell.detect_os()

    zshrc_result = zshrc.apply_zshrc(home, repo_path, profile, dry_run=dry_run)

    tool_results: list[tools.ToolResult] = []
    if not dry_run:
        all_tools = {t.name: t for t in config.load_tools(repo_path)}
        tool_results = tools.reconcile(profile.tools, all_tools, os_name, console=console)

    dotfile_results = dotfiles.apply_dotfiles(profile.dotfiles, home, repo_path, dry_run=dry_run, overwrite=overwrite)

    if not dry_run and current_state.has_attention:
        _clear_resolved_sync_state(current_state, home, repo_path)

    return ApplyResult(zshrc=zshrc_result, tools=tool_results, dotfiles=dotfile_results)


def _clear_resolved_sync_state(
    s: state.State,
    home: pathlib.Path,
    repo_path: pathlib.Path,
) -> None:
    """Remove sync state entries that are now resolved (live == repo on disk)."""

    def _resolved(path: str) -> bool:
        live = home / path
        repo_file = dotfiles.repo_path_for(path, repo_path)
        return live.exists() and repo_file.exists() and live.read_bytes() == repo_file.read_bytes()

    state.save_state(
        s.model_copy(
            update={
                "remote_updated": [p for p in s.remote_updated if not _resolved(p)],
                "conflict": [p for p in s.conflict if not _resolved(p)],
            }
        )
    )
