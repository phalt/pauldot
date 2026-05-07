"""Tool check, install, and update logic, OS-specific dispatch."""

import subprocess
import typing

import pydantic
from rich import console as rich_console

from pauldot import config


class ToolResult(pydantic.BaseModel):
    name: str
    action: typing.Literal["installed", "already_installed", "skipped", "failed", "updated", "not_installed"]
    error: str | None = None


def check(tool: config.ToolDefinition) -> bool:
    """Run the tool's check command. Returns True if the tool is present."""
    result = subprocess.run(tool.check, shell=True, capture_output=True)
    return result.returncode == 0


def install(
    tool: config.ToolDefinition,
    os_name: str,
    console: rich_console.Console | None = None,
) -> ToolResult:
    """Check if a tool is installed; install it if not. Streams subprocess output to the terminal.

    Tool install failures are reported but do not raise — see spec.md § Apply.
    """
    if check(tool):
        return ToolResult(name=tool.name, action="already_installed")

    install_cmd: str | None = getattr(tool.install, os_name, None)
    if install_cmd is None:
        return ToolResult(name=tool.name, action="skipped")

    if console:
        console.print(f"  → installing {tool.name}…", style="dim")

    result = subprocess.run(install_cmd, shell=True)
    if result.returncode != 0:
        return ToolResult(name=tool.name, action="failed", error=f"exit code {result.returncode}")
    return ToolResult(name=tool.name, action="installed")


def update(
    tool: config.ToolDefinition,
    os_name: str,
    console: rich_console.Console | None = None,
) -> ToolResult:
    """Run the tool's update command. Returns a ToolResult with action 'updated', 'skipped', or 'failed'."""
    if not check(tool):
        return ToolResult(name=tool.name, action="not_installed")

    update_cmd: str | None = getattr(tool.update, os_name, None)
    if update_cmd is None:
        return ToolResult(name=tool.name, action="skipped")

    if console:
        console.print(f"  → updating {tool.name}…", style="dim")

    result = subprocess.run(update_cmd, shell=True)
    if result.returncode != 0:
        return ToolResult(name=tool.name, action="failed", error=f"exit code {result.returncode}")
    return ToolResult(name=tool.name, action="updated")


def reconcile(
    tool_names: list[str],
    all_tools: dict[str, config.ToolDefinition],
    os_name: str,
    console: rich_console.Console | None = None,
) -> list[ToolResult]:
    """Reconcile a list of tool names against their definitions.

    Tools not defined in tools/tools.toml are reported as failed.
    Install failures do not abort the loop — see spec.md § Apply.
    """
    results = []
    for name in tool_names:
        if name not in all_tools:
            results.append(ToolResult(name=name, action="failed", error="not defined in tools/tools.toml"))
            continue
        results.append(install(all_tools[name], os_name, console=console))
    return results
