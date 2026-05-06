"""Tool check and install logic, OS-specific dispatch."""

import subprocess
import typing

import pydantic

from pauldot import config


class ToolResult(pydantic.BaseModel):
    name: str
    action: typing.Literal["installed", "already_installed", "skipped", "failed"]
    error: str | None = None
    output: str | None = None  # populated when verbose=True


def check(tool: config.ToolDefinition) -> bool:
    """Run the tool's check command. Returns True if the tool is present."""
    result = subprocess.run(tool.check, shell=True, capture_output=True)
    return result.returncode == 0


def install(tool: config.ToolDefinition, os_name: str, verbose: bool = False) -> ToolResult:
    """Check if a tool is installed; install it if not.

    Tool install failures are reported but do not raise — see spec.md § Apply.
    When verbose=True, subprocess stdout+stderr are captured in result.output.
    """
    if check(tool):
        return ToolResult(name=tool.name, action="already_installed")

    install_cmd: str | None = getattr(tool.install, os_name, None)
    if install_cmd is None:
        return ToolResult(name=tool.name, action="skipped")

    result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
    combined = "\n".join(filter(None, [result.stdout.strip(), result.stderr.strip()]))

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        return ToolResult(
            name=tool.name,
            action="failed",
            error=error,
            output=combined if verbose else None,
        )
    return ToolResult(
        name=tool.name,
        action="installed",
        output=combined if verbose else None,
    )


def reconcile(
    tool_names: list[str],
    all_tools: dict[str, config.ToolDefinition],
    os_name: str,
    verbose: bool = False,
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
        results.append(install(all_tools[name], os_name, verbose=verbose))
    return results
