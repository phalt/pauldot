"""Typer app entry point. Registers subcommand groups and top-level commands."""

import os
import pathlib
import shutil
import subprocess
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import absorb as pauldot_absorb
from pauldot import apply as pauldot_apply
from pauldot import config, display, dotfiles, git, profiles, scaffold, state, zshrc
from pauldot import migrate as pauldot_migrate
from pauldot import sync as pauldot_sync
from pauldot.commands import alias as cmd_alias
from pauldot.commands import help as cmd_help
from pauldot.commands import profile as cmd_profile
from pauldot.commands import tool as cmd_tool

_BANNER = (
    "\b\n"
    + r"""                   _     _       _
 _ __   __ _ _   _| | __| | ___ | |_
| '_ \ / _` | | | | |/ _` |/ _ \| __|
| |_) | (_| | |_| | | (_| | (_) | |_
| .__/ \__,_|\__,_|_|\__,_|\___/ \__|
|_|
personal system manager for bash aliases & tools"""
)

app = typer.Typer(no_args_is_help=True, help=_BANNER)

app.add_typer(cmd_alias.alias_app, name="alias", help="Manage shell aliases.", no_args_is_help=True)
app.add_typer(cmd_profile.profile_app, name="profile", help="Manage your dotfiles profile.", no_args_is_help=True)
app.add_typer(cmd_tool.tool_app, name="tool", help="Manage tools that can be installed.", no_args_is_help=True)
app.add_typer(
    cmd_help.help_app, name="help", help="Show instructions for setting up and using Pauldot.", no_args_is_help=True
)

console = rich_console.Console()


def _print_apply_result(result: pauldot_apply.ApplyResult, dry_run: bool) -> None:
    display.print_zshrc_result(result.zshrc, dry_run)
    display.print_dotfile_apply_results(result.dotfiles, dry_run=dry_run)
    if result.tools:
        cmd_tool.print_tool_results(result.tools)


def _gather_repo_url() -> str | None:
    return typer.prompt("Dotfiles repo URL")


def _gather_active_profile(default: str | None) -> str | None:
    return typer.prompt("Active profile", default=default)


@app.command()
def init(
    repo_url: typing.Annotated[str | None, typer.Argument()] = None,
    scaffold_path: typing.Annotated[
        pathlib.Path | None,
        typer.Option("--scaffold", help="Generate a starter dotfiles repo at this path instead of cloning."),
    ] = None,
) -> None:
    """Clone your dotfiles repo and configure this machine."""
    if scaffold_path is not None:
        try:
            created = scaffold.generate(scaffold_path)
        except FileExistsError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None

        console.print(f"✓ Scaffolded dotfiles repo at {scaffold_path}")
        for path in created:
            console.print(f"  {path.relative_to(scaffold_path)}", style="dim")

        console.print("\nNext steps:")
        console.print("  1. Edit pauldot.toml — set your profile and preferences.")
        console.print("  2. Edit bootstrap.sh — set PAULDOT_REPO to your repo URL.")
        console.print("  3. Push to GitHub and run `pauldot help fork` for the full walkthrough.")
        return

    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    if repo_path.exists():
        console.print(f"[yellow]⚠[/yellow] Dotfiles repo already exists at {repo_path}.")
        console.print("Run `pauldot sync` to update it.")
        raise typer.Exit(1)

    if repo_url is None:
        console.print("No dotfiles repo configured.\n")
        is_private = typer.confirm("Is your dotfiles repo private?", default=True)
        if is_private:
            console.print(
                "\nPrivate repos require GitHub CLI authentication. Run:\n\n"
                "    pauldot help gh\n\n"
                "…then re-run `pauldot init <repo-url>`."
            )
            raise typer.Exit(1)
        repo_url = _gather_repo_url()

    while repo_url is None:
        console.print("No dotfiles repo configured.\n")
        repo_url = _gather_repo_url()

    console.print(f"Cloning into {repo_path}…")
    try:
        git.clone(repo_url, repo_path)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    try:
        cfg = config.load_pauldot_config(repo_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    console.print("Repo cloned. Found pauldot.toml.\n")

    available = config.list_profiles(repo_path)
    default = cfg.core.default_profile
    console.print(f"Available profiles: {', '.join(available)}")
    console.print(f"Default: {default}\n")

    active = _gather_active_profile(default=default)
    while active not in available:
        console.print(f"[red]Error:[/red] Profile '{active}' not found. Available: {', '.join(available)}")
        active = _gather_active_profile(default=default)

    state.save_state(state.State(active_profile=active, repo_url=repo_url))
    console.print(f"Active profile: {active}")
    console.print("\nRun `pauldot apply` when ready.")


@app.command()
def apply(
    overwrite: typing.Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing live dotfiles with repo versions (backs up first)."),
    ] = False,
) -> None:
    """Reconcile current profile: write ~/.zshrc, install missing tools, bootstrap dotfiles."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), overwrite=overwrite, console=console)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_apply_result(result, dry_run=False)


@app.command()
def status() -> None:
    """Dry-run apply: show what would change without touching anything."""
    home = pathlib.Path.home()
    try:
        result = pauldot_apply.run(home, dry_run=True)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_apply_result(result, dry_run=True)

    repo_path = home / ".pauldot"
    try:
        s = state.load_state()
        profile = profiles.resolve(repo_path, s.active_profile)
        if profile.dotfiles:
            drift = dotfiles.status(profile.dotfiles, home, repo_path)
            display.print_dotfile_status_results(drift)
    except FileNotFoundError:
        pass

    try:
        ss = state.load_state()
        if ss.has_attention:
            console.print()
            console.print("[yellow]⚠[/yellow] Unresolved sync issues (run [bold]pauldot sync[/bold] for details):")
            for path, action in ss.all_pending():
                if action == "remote_updated":
                    console.print(f"  [cyan]↓[/cyan]  ~/{path} — remote has a newer version")
                elif action == "conflict":
                    console.print(f"  [red]⚠[/red]  ~/{path} — conflict: both sides changed")
    except FileNotFoundError:
        pass


@app.command()
def track(
    path: typing.Annotated[
        pathlib.Path, typer.Argument(help="Path to the file to track (absolute or relative to $HOME).")
    ],
) -> None:
    """Track a dotfile: copy it into the repo and add it to the active profile."""
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    resolved = path.expanduser().resolve()
    try:
        home_rel = str(resolved.relative_to(home))
    except ValueError:
        console.print(f"[red]Error:[/red] {path} is not inside your home directory.")
        raise typer.Exit(1) from None

    if not resolved.exists():
        console.print(f"[red]Error:[/red] {resolved} does not exist.")
        raise typer.Exit(1)
    if not resolved.is_file():
        console.print(f"[red]Error:[/red] {resolved} is not a regular file.")
        raise typer.Exit(1)

    try:
        s = state.load_state()
        profile = profiles.resolve(repo_path, s.active_profile)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if home_rel in profile.dotfiles:
        console.print(f"~/{home_rel} is already tracked in profile '{s.active_profile}'.")
        raise typer.Exit(0)

    repo_file = dotfiles.repo_path_for(home_rel, repo_path)
    repo_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, repo_file)

    config.add_dotfile_to_profile(repo_path, s.active_profile, home_rel)
    console.print(f"✓ Tracking ~/{home_rel} in profile '{s.active_profile}'.")
    console.print(f"  Repo copy: {repo_file.relative_to(repo_path)}")

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: track {home_rel}")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort


@app.command()
def edit(
    target: typing.Annotated[str, typer.Argument(help="What to edit: profile, tools, zshrc, pauldot")] = "pauldot",
) -> None:
    """Open a dotfiles file in $EDITOR."""
    editor = os.environ.get("EDITOR")
    if not editor:
        console.print("[red]Error:[/red] $EDITOR is not set. Set it in your profile's [env] block.")
        raise typer.Exit(1)

    repo_path = pathlib.Path.home() / ".pauldot"

    try:
        s = state.load_state()
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if target == "pauldot":
        path = repo_path / "pauldot.toml"
    elif target == "tools":
        path = repo_path / "tools" / "tools.toml"
    elif target == "profile":
        path = repo_path / "profiles" / f"{s.active_profile}.toml"
    elif target == "zshrc":
        try:
            profile = profiles.resolve(repo_path, s.active_profile)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None
        if not profile.zshrc_files:
            console.print(f"[red]Error:[/red] Profile '{s.active_profile}' has no zshrc file configured.")
            raise typer.Exit(1)
        path = profile.zshrc_files[-1]  # the most specific zshrc (child, not parent)
    else:
        console.print(f"[red]Error:[/red] Unknown target '{target}'. Choose: profile, tools, zshrc, pauldot")
        raise typer.Exit(1)

    subprocess.run([editor, str(path)])


@app.command()
def doctor() -> None:
    """Check pauldot's health on this machine."""
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    def ok(label: str, detail: str = "") -> None:
        t.add_row(rich_text.Text(f"✓  {label}", style="green"), rich_text.Text(detail, style="dim"))

    def warn(label: str, detail: str = "") -> None:
        t.add_row(rich_text.Text(f"⚠  {label}", style="yellow"), rich_text.Text(detail, style="dim"))

    def fail(label: str, detail: str = "") -> None:
        t.add_row(rich_text.Text(f"✗  {label}", style="red"), rich_text.Text(detail, style="dim"))

    # 1. state.toml
    try:
        s = state.load_state()
        ok("state.toml", f"profile: {s.active_profile}")
    except FileNotFoundError:
        fail("state.toml", "run `pauldot init <repo-url>`")
        s = None

    # 2. dotfiles repo
    if repo_path.exists():
        ok("dotfiles repo", str(repo_path))
    else:
        fail("dotfiles repo", f"{repo_path} not found")

    # 3. pauldot.toml
    try:
        cfg = config.load_pauldot_config(repo_path)
        ok("pauldot.toml")
    except FileNotFoundError:
        fail("pauldot.toml", "repo missing or not a pauldot dotfiles repo")
        cfg = None

    # 4. ~/.zshrc
    zshrc_link = home / ".zshrc"
    if zshrc_link.is_symlink():
        warn("~/.zshrc", "is a symlink (old pauldot model) — run `pauldot apply` to migrate")
    elif zshrc_link.exists():
        if zshrc_link.read_text().startswith(zshrc.PAULDOT_HEADER):
            ok("~/.zshrc", "managed by pauldot")
        else:
            warn("~/.zshrc", "exists but not managed by pauldot — run `pauldot apply`")
    else:
        warn("~/.zshrc", "not found — run `pauldot apply`")

    # 5. tracked dotfiles
    if s and repo_path.exists():
        try:
            profile = profiles.resolve(repo_path, s.active_profile)
            if profile.dotfiles:
                statuses = dotfiles.status(profile.dotfiles, home, repo_path)
                for ds in statuses:
                    if ds.state == "in_sync":
                        ok(f"~/{ds.path}", "in sync with repo")
                    elif ds.state == "drift":
                        warn(f"~/{ds.path}", "live differs from repo — run `pauldot sync`")
                    elif ds.state == "not_on_disk":
                        warn(f"~/{ds.path}", "missing — run `pauldot apply`")
                    elif ds.state == "not_in_repo":
                        warn(f"~/{ds.path}", "not in repo — run `pauldot track <path>`")
        except FileNotFoundError:
            pass

    # 6. unresolved sync issues
    if s:
        for path, action in s.all_pending():
            if action == "remote_updated":
                warn(f"~/{path}", "remote newer — run `pauldot apply --overwrite`")
            elif action == "conflict":
                fail(f"~/{path}", "conflict — resolve then run `pauldot sync`")

    # 7. gh binary (if private repo)
    if cfg and cfg.git.visibility == "private":
        if shutil.which("gh"):
            ok("gh binary")
        else:
            warn("gh binary", "not found — needed for private repos (`pauldot help gh`)")

    console.print(t)


@app.command()
def clean(
    yes: typing.Annotated[
        bool,
        typer.Option("--yes", "-y", help="Actually delete the backup files (default is dry-run)."),
    ] = False,
) -> None:
    """Remove backup files created by pauldot.

    Scans for .bak.<timestamp> files next to ~/.zshrc and each tracked dotfile.
    Runs as a dry-run by default — pass --yes to actually delete.
    """
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    # Collect the live paths pauldot manages: .zshrc plus tracked dotfiles.
    managed: list[pathlib.Path] = [home / ".zshrc"]
    try:
        s = state.load_state()
        profile = profiles.resolve(repo_path, s.active_profile)
        for rel in profile.dotfiles:
            managed.append(home / rel)
    except FileNotFoundError:
        pass

    backups: list[pathlib.Path] = []
    for live in managed:
        # Glob for siblings named <original>.bak.<anything>
        backups.extend(sorted(live.parent.glob(f"{live.name}.bak.*")))

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
        return

    for b in backups:
        b.unlink()
    console.print(f"\n✓ Deleted {len(backups)} backup(s).")


@app.command()
def sync() -> None:
    """Sync dotfiles: pull remote changes first, then push any local edits."""
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    if not repo_path.exists():
        console.print("[red]Error:[/red] Dotfiles repo not found. Run `pauldot init <repo-url>`.")
        raise typer.Exit(1)

    try:
        result = pauldot_sync.run(home)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if result.blocked_by_state:
        console.print("[yellow]⚠[/yellow] Sync blocked — unresolved issues from a previous sync:\n")
        for r in result.blocked_by_state:
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
        raise typer.Exit(1)

    if result.sync_results:
        display.print_dotfile_sync_results(result.sync_results)

    needs_attention = [r for r in result.sync_results if r.action in ("remote_updated", "conflict")]
    if needs_attention:
        console.print()
        for r in needs_attention:
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
        raise typer.Exit(1)

    if result.committed:
        console.print("✓ Committed local dotfile changes.")
    if result.pushed:
        console.print("✓ Pushed.")
    else:
        console.print("  Nothing to push.")


@app.command()
def absorb(
    target: typing.Annotated[
        str,
        typer.Option("--target", help="Source file to absorb into (relative to files/)."),
    ] = "zshrc.base",
    dry_run: typing.Annotated[
        bool, typer.Option("--dry-run", help="Show what would be absorbed without writing anything.")
    ] = False,
) -> None:
    """Absorb external zshrc modifications back into your dotfiles source files.

    Diffs .zshrc.generated against what pauldot would generate and appends the
    extra lines (written by tools like nvm, pyenv, brew) to the target source file.
    """
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    try:
        result = pauldot_absorb.absorb(home, repo_path, target_name=target, dry_run=dry_run)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if not result.lines:
        console.print("Nothing to absorb.")
        return

    if dry_run:
        console.print(f"Would absorb {len(result.lines)} line(s) into files/{target}:\n")
        for line in result.lines:
            console.print(f"  {line}", style="dim")
        return

    console.print(f"✓ Absorbed {len(result.lines)} line(s) into {result.target}")

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, "pauldot: absorb zshrc modifications")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort


@app.command()
def migrate(
    dry_run: typing.Annotated[
        bool, typer.Option("--dry-run", help="Show what would be migrated without writing anything.")
    ] = False,
) -> None:
    """Migrate an existing ~/.zshrc into your pauldot dotfiles repo.

    Splits aliases into files/aliases.zsh and everything else into files/zshrc.base.
    Run this once on a machine that already has a ~/.zshrc before running `pauldot apply`.
    """
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    if not repo_path.exists():
        console.print("[red]Error:[/red] Dotfiles repo not found. Run `pauldot init <repo-url>` first.")
        raise typer.Exit(1)

    try:
        result = pauldot_migrate.migrate(home, repo_path, dry_run=dry_run)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

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
            rich_text.Text(
                f"{len(result.aliases_skipped)} alias(es) already defined",
                style="dim",
            ),
        )
    console.print(t)

    if dry_run:
        return

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, "pauldot: migrate existing zshrc")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort

    console.print("\nReview the changes, then run `pauldot apply` when ready.")
