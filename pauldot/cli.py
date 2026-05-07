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
from pauldot import config, display, git, profiles, scaffold, state, zshrc
from pauldot import migrate as pauldot_migrate
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
def apply() -> None:
    """Reconcile current profile: write ~/.zshrc, install missing tools."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), console=console)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_apply_result(result, dry_run=False)


@app.command()
def status() -> None:
    """Dry-run apply: show what would change without touching anything."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), dry_run=True)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_apply_result(result, dry_run=True)


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

    # 5. gh binary (if private repo)
    if cfg and cfg.git.visibility == "private":
        if shutil.which("gh"):
            ok("gh binary")
        else:
            warn("gh binary", "not found — needed for private repos (`pauldot help gh`)")

    console.print(t)


@app.command()
def sync() -> None:
    """Pull latest changes from remote; push if there are local commits."""
    repo_path = pathlib.Path.home() / ".pauldot"

    if not repo_path.exists():
        console.print("[red]Error:[/red] Dotfiles repo not found. Run `pauldot init <repo-url>`.")
        raise typer.Exit(1)

    if git.has_uncommitted_changes(repo_path):
        try:
            cfg = config.load_pauldot_config(repo_path)
            if cfg.git.auto_commit:
                git.commit(repo_path, "pauldot: commit local changes before sync")
                console.print("✓ Committed local changes.")
            else:
                console.print(
                    "[red]Error:[/red] You have uncommitted changes.\n"
                    "Commit or stash them before syncing, or set auto_commit = true in pauldot.toml."
                )
                raise typer.Exit(1)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None

    try:
        output = git.pull_rebase(repo_path)
        if output:
            console.print(output)
        console.print("✓ Pulled latest changes.")
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if git.has_unpushed_commits(repo_path):
        try:
            git.push(repo_path)
            console.print("✓ Pushed local commits.")
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None
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
