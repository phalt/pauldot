"""Typer app, command definitions, and subcommand groups."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import apply as pauldot_apply
from pauldot import config, git, state, zshrc

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
def init(
    repo_url: typing.Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Clone your dotfiles repo and configure this machine."""
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
        repo_url = typer.prompt("Dotfiles repo URL")

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

    active = typer.prompt("Set active profile", default=default)
    if active not in available:
        console.print(f"[red]Error:[/red] Profile '{active}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)

    state.save_state(state.State(active_profile=active, repo_url=repo_url))
    console.print(f"Active profile: {active}")
    console.print("\nRun `pauldot apply` when ready.")


@app.command()
def apply() -> None:
    """Reconcile current profile: symlink ~/.zshrc, install missing tools."""
    try:
        result = pauldot_apply.run(pathlib.Path.home())
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_zshrc_result(result, dry_run=False)


@app.command()
def status() -> None:
    """Dry-run apply: show what would change without touching anything."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), dry_run=True)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    _print_zshrc_result(result, dry_run=True)


# — profile subcommands ————————————————————————————————————————————————————————


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
        marker = rich_text.Text(f"  {name}")
        if name == active:
            marker.stylize("bold green")
            marker = marker + rich_text.Text(" (active)", style="dim")
        console.print(marker)


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
