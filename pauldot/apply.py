"""The reconciliation engine: load state → resolve profile → write ~/.zshrc → reconcile tools."""

import pathlib

import pydantic

from pauldot import config, profiles, shell, state, tools, zshrc


class ApplyResult(pydantic.BaseModel):
    zshrc: zshrc.ZshrcResult
    tools: list[tools.ToolResult]


def run(home: pathlib.Path, dry_run: bool = False, verbose: bool = False) -> ApplyResult:
    """Run the apply pipeline.

    Loads state and config, resolves the active profile, writes ~/.zshrc as a plain file,
    and reconciles tools. In dry_run mode only the zshrc step runs (idempotent read + describe);
    tools are skipped. When verbose=True, subprocess output from tool installs is captured
    in each ToolResult.
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
        tool_results = tools.reconcile(profile.tools, all_tools, os_name, verbose=verbose)

    return ApplyResult(zshrc=zshrc_result, tools=tool_results)
