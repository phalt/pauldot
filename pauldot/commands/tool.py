"""Tool subcommands: list, install, add, remove."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import config, git, profiles, shell, state, tools

tool_app = typer.Typer()

console = rich_console.Console()

_TOOL_ACTION_LABELS: dict[str, tuple[str, str]] = {
    "installed": ("✓ installed", "green"),
    "already_installed": ("✓ already installed", "dim"),
    "skipped": ("– skipped", "dim"),
    "failed": ("⚠ failed", "yellow"),
}


def print_tool_results(tool_results: list[tools.ToolResult]) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    for result in tool_results:
        label, style = _TOOL_ACTION_LABELS[result.action]
        error_text = rich_text.Text(result.error or "", style="dim")
        t.add_row(rich_text.Text(result.name), rich_text.Text(label, style=style), error_text)
        if result.output:
            for line in result.output.splitlines():
                t.add_row(rich_text.Text(""), rich_text.Text(f"  {line}", style="dim"), rich_text.Text(""))

    console.print(t)


@tool_app.command("list")
def tool_list() -> None:
    """List all tools defined in tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    all_tools = config.load_tools(repo_path)

    if not all_tools:
        console.print("No tools defined. Run `pauldot tool add` to add one.")
        return

    try:
        active_profile = profiles.resolve(repo_path, state.load_state().active_profile)
        profile_tools = set(active_profile.tools)
    except FileNotFoundError:
        profile_tools = set()

    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    for tool_def in all_tools:
        is_installed = tools.check(tool_def)
        status_text = rich_text.Text(
            "✓ installed" if is_installed else "✗ not installed",
            style="green" if is_installed else "red",
        )
        profile_marker = rich_text.Text(
            " (active profile)" if tool_def.name in profile_tools else "",
            style="dim",
        )
        t.add_row(rich_text.Text(tool_def.name), status_text, profile_marker)

    console.print(t)


@tool_app.command("install")
def tool_install(
    name: typing.Annotated[str | None, typer.Argument()] = None,
    verbose: typing.Annotated[
        bool, typer.Option("--verbose", "-v", help="Show subprocess output from install commands.")
    ] = False,
) -> None:
    """Install a specific tool, or all tools in the active profile."""
    repo_path = pathlib.Path.home() / ".pauldot"
    all_tools = {t.name: t for t in config.load_tools(repo_path)}
    os_name = shell.detect_os()

    if name is not None:
        if name not in all_tools:
            console.print(f"[red]Error:[/red] Tool '{name}' not found. Run `pauldot tool list`.")
            raise typer.Exit(1)
        tool_names = [name]
    else:
        try:
            active = state.load_state().active_profile
            profile = profiles.resolve(repo_path, active)
            tool_names = profile.tools
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None

    results = tools.reconcile(tool_names, all_tools, os_name, verbose=verbose)
    print_tool_results(results)


@tool_app.command("add")
def tool_add() -> None:
    """Interactively add a tool definition to tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"

    name = typer.prompt("Tool name")
    check_cmd = typer.prompt("Check command (e.g. command -v uv)")
    macos_install = typer.prompt("macOS install command (leave blank to skip)", default="")
    linux_install = typer.prompt("Linux install command (leave blank to skip)", default="")

    existing = config.load_tools(repo_path)
    if any(t.name == name for t in existing):
        console.print(f"[yellow]⚠[/yellow] Tool '{name}' already defined. Edit tools/tools.toml to update it.")
        raise typer.Exit(1)

    new_tool = config.ToolDefinition(
        name=name,
        check=check_cmd,
        install=config.ToolInstall(
            macos=macos_install or None,
            linux=linux_install or None,
        ),
    )
    config.save_tools(repo_path, [*existing, new_tool])
    console.print(f"✓ Added '{name}' to tools/tools.toml.")

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: add tool {name}")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort


@tool_app.command("remove")
def tool_remove(name: str) -> None:
    """Remove a tool definition from tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    existing = config.load_tools(repo_path)
    updated = [t for t in existing if t.name != name]

    if len(updated) == len(existing):
        console.print(f"[red]Error:[/red] Tool '{name}' not found. Run `pauldot tool list`.")
        raise typer.Exit(1)

    config.save_tools(repo_path, updated)
    console.print(f"✓ Removed '{name}' from tools/tools.toml.")

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: remove tool {name}")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort
