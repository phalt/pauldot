"""Shared rich display helpers for pauldot commands."""

import pathlib
import typing

import pydantic
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import absorb as pauldot_absorb
from pauldot import dotfiles, state, zshrc
from pauldot import migrate as pauldot_migrate

console = rich_console.Console()

# ---------------------------------------------------------------------------
# zshrc
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# dotfiles
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


class DoctorCheck(pydantic.BaseModel):
    status: typing.Literal["ok", "warn", "fail"]
    label: str
    detail: str = ""


_DOCTOR_ICONS: dict[str, tuple[str, str]] = {
    "ok": ("✓", "green"),
    "warn": ("⚠", "yellow"),
    "fail": ("✗", "red"),
}


def print_doctor_result(checks: list[DoctorCheck]) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    for check in checks:
        icon, style = _DOCTOR_ICONS[check.status]
        t.add_row(
            rich_text.Text(f"{icon}  {check.label}", style=style),
            rich_text.Text(check.detail, style="dim"),
        )
    console.print(t)


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


def print_clean_result(backups: list[pathlib.Path], home: pathlib.Path, yes: bool) -> None:
    if not backups:
        console.print("No backup files found.")
        return
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    for b in backups:
        rel = b.relative_to(home)
        action = rich_text.Text("✓ deleted", style="green") if yes else rich_text.Text("would delete", style="dim")
        t.add_row(rich_text.Text(f"~/{rel}"), action)
    console.print(t)
    if not yes:
        console.print(f"\n{len(backups)} backup(s) found. Run [bold]pauldot clean --yes[/bold] to delete them.")


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


def print_sync_blocked(blocked: list[dotfiles.DotfileSyncResult]) -> None:
    console.print("[yellow]⚠[/yellow] Sync blocked — unresolved issues from a previous sync:\n")
    for r in blocked:
        if r.action == "remote_updated":
            console.print(
                f"  [cyan]↓[/cyan]  ~/{r.path} — remote has a newer version.\n"
                f"     Run [bold]pauldot apply --overwrite[/bold] to update your local file."
            )
        elif r.action == "conflict":
            console.print(
                f"  [red]⚠[/red]  ~/{r.path} — conflict: both sides changed.\n"
                f"     Resolve manually or run [bold]pauldot apply --overwrite[/bold] to accept the remote version."
            )
    console.print()


def print_sync_attention(results: list[dotfiles.DotfileSyncResult]) -> None:
    console.print()
    for r in results:
        if r.action == "remote_updated":
            console.print(
                f"[cyan]↓[/cyan]  ~/{r.path} — remote has a newer version.\n"
                f"   Run [bold]pauldot apply --overwrite[/bold] to update your local file."
            )
        elif r.action == "conflict":
            console.print(
                f"[red]⚠[/red]  ~/{r.path} — both sides changed.\n"
                f"   Resolve manually, then run [bold]pauldot sync[/bold] again.\n"
                f"   Or run [bold]pauldot apply --overwrite[/bold] to accept the remote version."
            )
    console.print("[yellow]⚠[/yellow] Resolve the above before pushing. Exiting without push.")


def print_sync_committed_pushed(committed: bool, pushed: bool) -> None:
    if committed:
        console.print("✓ Committed local dotfile changes.")
    if pushed:
        console.print("✓ Pushed.")
    else:
        console.print("  Nothing to push.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def print_status_attention(s: state.State) -> None:
    if not s.has_attention:
        return
    console.print()
    console.print("[yellow]⚠[/yellow] Unresolved sync issues (run [bold]pauldot sync[/bold] for details):")
    for path, action in s.all_pending():
        if action == "remote_updated":
            console.print(f"  [cyan]↓[/cyan]  ~/{path} — remote has a newer version")
        elif action == "conflict":
            console.print(f"  [red]⚠[/red]  ~/{path} — conflict: both sides changed")


# ---------------------------------------------------------------------------
# absorb
# ---------------------------------------------------------------------------


def print_absorb_result(result: pauldot_absorb.AbsorbResult, target_name: str, dry_run: bool) -> None:
    if not result.lines:
        console.print("Nothing to absorb.")
        return
    if dry_run:
        console.print(f"Would absorb {len(result.lines)} line(s) into files/{target_name}:\n")
        for line in result.lines:
            console.print(f"  {line}", style="dim")
        return
    console.print(f"✓ Absorbed {len(result.lines)} line(s) into {result.target}")


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


def print_migrate_result(result: pauldot_migrate.MigrateResult, dry_run: bool) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    prefix = "Would migrate" if dry_run else "✓ Migrated"
    t.add_row(
        rich_text.Text("files/zshrc.base", style="bold"),
        rich_text.Text(f"{prefix} {result.zshrc_line_count} line(s)", style="dim" if dry_run else "green"),
    )
    t.add_row(
        rich_text.Text("files/aliases.zsh", style="bold"),
        rich_text.Text(f"{prefix} {len(result.aliases_added)} alias(es)", style="dim" if dry_run else "green"),
    )
    if result.aliases_skipped:
        t.add_row(
            rich_text.Text("  skipped", style="dim"),
            rich_text.Text(f"{len(result.aliases_skipped)} alias(es) already defined", style="dim"),
        )
    console.print(t)
