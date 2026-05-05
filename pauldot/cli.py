"""Typer app, command definitions, and subcommand groups."""

import pathlib

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import zshrc

app = typer.Typer(no_args_is_help=True)
profile_app = typer.Typer()
tool_app = typer.Typer()
keys_app = typer.Typer()
secret_app = typer.Typer()
help_app = typer.Typer()

app.add_typer(profile_app, name="profile")
app.add_typer(tool_app, name="tool")
app.add_typer(keys_app, name="keys")
app.add_typer(secret_app, name="secret")
app.add_typer(help_app, name="help")

console = rich_console.Console()

_ACTION_LABELS: dict[str, rich_text.Text] = {
    "created": rich_text.Text("✓ created", style="green"),
    "backup_replaced": rich_text.Text("✓ replaced", style="green"),
    "replaced": rich_text.Text("✓ replaced", style="green"),
    "no_op": rich_text.Text("✓ already linked", style="dim"),
}


def _print_zshrc_result(result: zshrc.ZshrcResult, dry_run: bool) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    action = _ACTION_LABELS[result.action]
    if dry_run:
        action = action + rich_text.Text(" (dry run)", style="dim")

    t.add_row(rich_text.Text("~/.zshrc", style="bold"), action)
    t.add_row(rich_text.Text("  → target", style="dim"), rich_text.Text(str(result.target)))
    if result.backup:
        t.add_row(rich_text.Text("  → backup", style="dim"), rich_text.Text(str(result.backup)))

    console.print(t)


@app.command()
def apply() -> None:
    """Reconcile current profile: symlink ~/.zshrc, install missing tools."""
    try:
        result = zshrc.apply_zshrc(pathlib.Path.home())
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_zshrc_result(result, dry_run=False)


@app.command()
def status() -> None:
    """Dry-run apply: show what would change without touching anything."""
    try:
        result = zshrc.apply_zshrc(pathlib.Path.home(), dry_run=True)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_zshrc_result(result, dry_run=True)
