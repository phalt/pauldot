"""Tool subcommands: list, install, add, remove, update."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import config, display, git, profiles, shell, state, tools

tool_app = typer.Typer()

console = rich_console.Console()


def _maybe_commit(repo_path: pathlib.Path, message: str) -> None:
    """Commit repo changes when auto_commit is enabled. Silently no-ops on any error."""
    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, message)
            console.print("✓ Committed to dotfiles repo.")
    except (FileNotFoundError, RuntimeError):
        pass


@tool_app.command("list")
def tool_list() -> None:
    """List all tools defined in tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    all_tools = config.load_tools(repo_path)

    if not all_tools:
        console.print("No tools defined. Run `pauldot tool add` to add one.")
        return

    profile_names = config.list_profiles(repo_path)
    tool_profiles: dict[str, list[str]] = {t.name: [] for t in all_tools}
    for profile_name in profile_names:
        try:
            p = config.load_profile(repo_path, profile_name)
            for tool_name in p.tools:
                if tool_name in tool_profiles:
                    tool_profiles[tool_name].append(profile_name)
        except FileNotFoundError:
            pass

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
        profiles_text = rich_text.Text(
            ", ".join(tool_profiles.get(tool_def.name, [])) or "–",
            style="dim",
        )
        t.add_row(rich_text.Text(tool_def.name), status_text, profiles_text)

    console.print(t)


@tool_app.command("install")
def tool_install(
    name: typing.Annotated[str | None, typer.Argument()] = None,
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

    results = tools.reconcile(tool_names, all_tools, os_name, console=console)
    display.print_tool_results(results)


@tool_app.command("update")
def tool_update(
    name: typing.Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Update a specific tool, or all tools in the active profile."""
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

    results = [tools.update(all_tools[n], os_name, console=console) for n in tool_names if n in all_tools]
    display.print_tool_results(results)


@tool_app.command("add")
def tool_add(
    profile_name: typing.Annotated[
        str | None, typer.Option("--profile", help="Add tool to this profile's tools list. Defaults to base.")
    ] = None,
) -> None:
    """Interactively add a tool definition to tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    target_profile = profile_name or "base"

    name = typer.prompt("Tool name")

    existing_tools = {t.name: t for t in config.load_tools(repo_path)}

    if name in existing_tools:
        try:
            resolved = profiles.resolve(repo_path, target_profile)
            if name in resolved.tools:
                console.print(f"Tool '{name}' is already in profile '{target_profile}'.")
                raise typer.Exit(0)
        except FileNotFoundError:
            pass
        console.print(f"Tool '{name}' is already defined — adding to profile '{target_profile}'.")
        config.add_tool_to_profile(repo_path, target_profile, name)
        console.print(f"✓ Added '{name}' to profile '{target_profile}'.")
        return

    check_cmd = typer.prompt("Check command (e.g. command -v uv)")
    macos_install = typer.prompt("macOS install command (leave blank to skip)", default="")
    linux_install = typer.prompt("Linux install command (leave blank to skip)", default="")
    macos_update = typer.prompt("macOS update command (leave blank to skip)", default="")
    linux_update = typer.prompt("Linux update command (leave blank to skip)", default="")

    new_tool = config.ToolDefinition(
        name=name,
        check=check_cmd,
        install=config.ToolInstall(
            macos=macos_install or None,
            linux=linux_install or None,
        ),
        update=config.ToolUpdate(
            macos=macos_update or None,
            linux=linux_update or None,
        ),
    )
    existing = list(existing_tools.values())
    config.save_tools(repo_path, [*existing, new_tool])
    console.print(f"✓ Added '{name}' to tools/tools.toml.")

    try:
        config.add_tool_to_profile(repo_path, target_profile, name)
        console.print(f"✓ Added '{name}' to profile '{target_profile}'.")
    except FileNotFoundError:
        console.print(f"[yellow]⚠[/yellow] Profile '{target_profile}' not found — tool saved to tools.toml only.")

    _maybe_commit(repo_path, f"pauldot: add tool {name}")


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

    _maybe_commit(repo_path, f"pauldot: remove tool {name}")
