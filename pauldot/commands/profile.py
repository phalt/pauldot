"""Profile subcommands: show, list, set."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import text as rich_text

from pauldot import apply as pauldot_apply
from pauldot import config, display, state

profile_app = typer.Typer()

console = rich_console.Console()


@profile_app.command("list")
def profile_list() -> None:
    """List available profiles. Show active."""
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
def profile_set(
    name: str,
    apply_after: typing.Annotated[
        bool,
        typer.Option("--apply", help="Apply immediately after setting the active profile."),
    ] = False,
) -> None:
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

    if apply_after or typer.confirm("Apply now?", default=True):
        try:
            result = pauldot_apply.run(pathlib.Path.home())
            display.print_zshrc_result(result.zshrc, dry_run=False)
        except (FileNotFoundError, RuntimeError) as e:
            console.print(f"[yellow]⚠[/yellow] Apply failed: {e}")
    else:
        console.print("Run `pauldot apply` when ready.")
