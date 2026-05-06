"""Profile subcommands: show, list, set."""

import pathlib

import typer
from rich import console as rich_console
from rich import text as rich_text

from pauldot import config, state

profile_app = typer.Typer()

console = rich_console.Console()


@profile_app.command("show")
def profile_show() -> None:
    """Show the active profile."""
    try:
        s = state.load_state()
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    console.print(s.active_profile)


@profile_app.command("list")
def profile_list() -> None:
    """List available profiles."""
    repo_path = pathlib.Path.home() / ".pauldot"
    available = config.list_profiles(repo_path)

    try:
        active = state.load_state().active_profile
    except FileNotFoundError:
        active = None

    for name in available:
        entry = rich_text.Text(f"  {name}")
        if name == active:
            entry.stylize("bold green")
            entry = entry + rich_text.Text(" (active)", style="dim")
        console.print(entry)


@profile_app.command("set")
def profile_set(name: str) -> None:
    """Set the active profile."""
    repo_path = pathlib.Path.home() / ".pauldot"
    available = config.list_profiles(repo_path)

    if name not in available:
        console.print(f"[red]Error:[/red] Profile '{name}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)

    try:
        s = state.load_state()
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    s.active_profile = name
    state.save_state(s)
    console.print(f"Active profile: {name}")
