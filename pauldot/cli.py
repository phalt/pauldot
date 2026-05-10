"""Typer app entry point. Registers subcommand groups and top-level commands."""

import os
import pathlib
import shutil
import subprocess
import typing

import typer
from rich import console as rich_console

from pauldot import __version__, config, display, dotfiles, git, profiles, scaffold, state, zshrc
from pauldot import absorb as pauldot_absorb
from pauldot import apply as pauldot_apply
from pauldot import migrate as pauldot_migrate
from pauldot import sync as pauldot_sync
from pauldot.commands import alias as cmd_alias
from pauldot.commands import help as cmd_help
from pauldot.commands import profile as cmd_profile
from pauldot.commands import tool as cmd_tool

_BANNER = (
    "\b\n"
    + rf"""                   _     _       _
 _ __   __ _ _   _| | __| | ___ | |_
| '_ \ / _` | | | | |/ _` |/ _ \| __|
| |_) | (_| | |_| | | (_| | (_) | |_
| .__/ \__,_|\__,_|_|\__,_|\___/ \__|
|_|

Pauldot. Version: {__version__}

Terminal and tooling config manager.

Docs: https://phalt.github.io/pauldot/

Written by: https://paulwrites.software"""
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
    """Apply the current profile."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), overwrite=overwrite, console=console)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_apply_result(result, dry_run=False)


@app.command()
def version() -> None:
    """Print the current version of pauldot."""
    console.print(f"pauldot version {__version__}")


@app.command()
def status() -> None:
    """Show what would change without touching anything."""
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
        display.print_status_attention(ss)
    except FileNotFoundError:
        pass


@app.command()
def track(
    path: typing.Annotated[
        pathlib.Path, typer.Argument(help="Path to the file to track (absolute or relative to $HOME).")
    ],
) -> None:
    """Track a dotfile."""
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

    checks: list[display.DoctorCheck] = []

    # 1. state.toml
    s = None
    try:
        s = state.load_state()
        checks.append(display.DoctorCheck(status="ok", label="state.toml", detail=f"profile: {s.active_profile}"))
    except FileNotFoundError:
        checks.append(display.DoctorCheck(status="fail", label="state.toml", detail="run `pauldot init <repo-url>`"))

    # 2. dotfiles repo
    if repo_path.exists():
        checks.append(display.DoctorCheck(status="ok", label="dotfiles repo", detail=str(repo_path)))
    else:
        checks.append(display.DoctorCheck(status="fail", label="dotfiles repo", detail=f"{repo_path} not found"))

    # 3. pauldot.toml
    cfg = None
    try:
        cfg = config.load_pauldot_config(repo_path)
        checks.append(display.DoctorCheck(status="ok", label="pauldot.toml"))
    except FileNotFoundError:
        checks.append(
            display.DoctorCheck(
                status="fail", label="pauldot.toml", detail="repo missing or not a pauldot dotfiles repo"
            )
        )

    # 4. ~/.zshrc
    zshrc_path = home / ".zshrc"
    if zshrc_path.is_symlink():
        checks.append(
            display.DoctorCheck(
                status="warn",
                label="~/.zshrc",
                detail="is a symlink (old pauldot model) — run `pauldot apply` to migrate",
            )
        )
    elif zshrc_path.exists():
        if zshrc_path.read_text().startswith(zshrc.PAULDOT_HEADER):
            checks.append(display.DoctorCheck(status="ok", label="~/.zshrc", detail="managed by pauldot"))
        else:
            checks.append(
                display.DoctorCheck(
                    status="warn", label="~/.zshrc", detail="exists but not managed by pauldot — run `pauldot apply`"
                )
            )
    else:
        checks.append(display.DoctorCheck(status="warn", label="~/.zshrc", detail="not found — run `pauldot apply`"))

    # 5. tracked dotfiles
    if s and repo_path.exists():
        try:
            profile = profiles.resolve(repo_path, s.active_profile)
            if profile.dotfiles:
                statuses = dotfiles.status(profile.dotfiles, home, repo_path)
                for ds in statuses:
                    if ds.state == "in_sync":
                        checks.append(
                            display.DoctorCheck(status="ok", label=f"~/{ds.path}", detail="in sync with repo")
                        )
                    elif ds.state == "drift":
                        checks.append(
                            display.DoctorCheck(
                                status="warn",
                                label=f"~/{ds.path}",
                                detail="live differs from repo — run `pauldot sync`",
                            )
                        )
                    elif ds.state == "not_on_disk":
                        checks.append(
                            display.DoctorCheck(
                                status="warn", label=f"~/{ds.path}", detail="missing — run `pauldot apply`"
                            )
                        )
                    elif ds.state == "not_in_repo":
                        checks.append(
                            display.DoctorCheck(
                                status="warn", label=f"~/{ds.path}", detail="not in repo — run `pauldot track <path>`"
                            )
                        )
        except FileNotFoundError:
            pass

    # 6. unresolved sync issues
    if s:
        for path, action in s.all_pending():
            if action == "remote_updated":
                checks.append(
                    display.DoctorCheck(
                        status="warn", label=f"~/{path}", detail="remote newer — run `pauldot apply --overwrite`"
                    )
                )
            elif action == "conflict":
                checks.append(
                    display.DoctorCheck(
                        status="fail", label=f"~/{path}", detail="conflict — resolve then run `pauldot sync`"
                    )
                )

    # 7. gh binary (if private repo)
    if cfg and cfg.git.visibility == "private":
        if shutil.which("gh"):
            checks.append(display.DoctorCheck(status="ok", label="gh binary"))
        else:
            checks.append(
                display.DoctorCheck(
                    status="warn", label="gh binary", detail="not found — needed for private repos (`pauldot help gh`)"
                )
            )

    display.print_doctor_result(checks)


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
        backups.extend(sorted(live.parent.glob(f"{live.name}.bak.*")))

    display.print_clean_result(backups, home, yes)

    if not backups or not yes:
        return

    for b in backups:
        b.unlink()
    console.print(f"\n✓ Deleted {len(backups)} backup(s).")


@app.command()
def sync() -> None:
    """Pull remote changes first, then push any local edits."""
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
        display.print_sync_blocked(result.blocked_by_state)
        raise typer.Exit(1)

    if result.sync_results:
        display.print_dotfile_sync_results(result.sync_results)

    needs_attention = [r for r in result.sync_results if r.action in ("remote_updated", "conflict")]
    if needs_attention:
        display.print_sync_attention(needs_attention)
        raise typer.Exit(1)

    display.print_sync_committed_pushed(result.committed, result.pushed)


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
    """Absorb external zshrc modifications.

    Diffs ~/.zshrc against what pauldot would generate and appends the
    extra lines (written by tools like nvm, pyenv, brew) to the target source file.
    """
    home = pathlib.Path.home()
    repo_path = home / ".pauldot"

    try:
        result = pauldot_absorb.absorb(home, repo_path, target_name=target, dry_run=dry_run)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    display.print_absorb_result(result, target, dry_run)

    if not result.lines or dry_run:
        return

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
    """Migrate an existing ~/.zshrc. Use when setting up pauldot on a new machine.

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

    display.print_migrate_result(result, dry_run)

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
