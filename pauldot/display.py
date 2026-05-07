"""Shared rich display helpers for pauldot commands."""

from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import zshrc

console = rich_console.Console()

_ZSHRC_ACTION_LABELS: dict[str, rich_text.Text] = {
    "created": rich_text.Text("✓ created", style="green"),
    "written": rich_text.Text("✓ updated", style="green"),
    "backup_replaced": rich_text.Text("✓ replaced", style="green"),
    "no_op": rich_text.Text("✓ up to date", style="dim"),
}


def print_zshrc_result(result: zshrc.ZshrcResult, dry_run: bool) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    action = _ZSHRC_ACTION_LABELS[result.action]
    if dry_run:
        action = action + rich_text.Text(" (dry run)", style="dim")

    t.add_row(rich_text.Text("~/.zshrc", style="bold"), action)
    if result.backup:
        t.add_row(rich_text.Text("  → backup", style="dim"), rich_text.Text(str(result.backup)))

    console.print(t)
