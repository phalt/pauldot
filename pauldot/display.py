"""Shared rich display helpers for pauldot commands."""

from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import dotfiles, zshrc

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


_DOTFILE_APPLY_LABELS: dict[str, tuple[str, str]] = {
    "copied": ("✓ copied", "green"),
    "overwritten": ("✓ overwritten", "green"),
    "already_present": ("✓ already present", "dim"),
    "missing_source": ("⚠ missing source", "yellow"),
}

_DOTFILE_SYNC_LABELS: dict[str, tuple[str, str]] = {
    "no_change": ("✓ no change", "dim"),
    "synced": ("✓ synced", "green"),
    "remote_updated": ("↓ remote updated", "cyan"),
    "conflict": ("⚠ conflict", "red"),
    "missing_live": ("⚠ missing live file", "yellow"),
}

_DOTFILE_STATUS_LABELS: dict[str, tuple[str, str]] = {
    "in_sync": ("✓ in sync", "dim"),
    "drift": ("⚠ drift", "yellow"),
    "not_in_repo": ("⚠ not in repo", "yellow"),
    "not_on_disk": ("⚠ not on disk", "yellow"),
}


def print_dotfile_apply_results(results: list[dotfiles.DotfileApplyResult], dry_run: bool = False) -> None:
    if not results:
        return
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    for result in results:
        label, style = _DOTFILE_APPLY_LABELS[result.action]
        if dry_run:
            label += " (dry run)"
        t.add_row(rich_text.Text(f"~/{result.path}"), rich_text.Text(label, style=style))
        if result.backup:
            t.add_row(rich_text.Text("  → backup", style="dim"), rich_text.Text(str(result.backup), style="dim"))
    console.print(t)


def print_dotfile_sync_results(results: list[dotfiles.DotfileSyncResult]) -> None:
    if not results:
        return
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    for result in results:
        label, style = _DOTFILE_SYNC_LABELS[result.action]
        t.add_row(rich_text.Text(f"~/{result.path}"), rich_text.Text(label, style=style))
    console.print(t)


def print_dotfile_status_results(results: list[dotfiles.DotfileStatus]) -> None:
    if not results:
        return
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    hints: dict[str, str] = {
        "drift": "run pauldot sync",
        "not_in_repo": "run pauldot track <path>",
        "not_on_disk": "run pauldot apply",
    }
    for result in results:
        label, style = _DOTFILE_STATUS_LABELS[result.state]
        hint = rich_text.Text(hints.get(result.state, ""), style="dim")
        t.add_row(rich_text.Text(f"~/{result.path}"), rich_text.Text(label, style=style), hint)
    console.print(t)
