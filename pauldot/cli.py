"""Typer app, command definitions, and subcommand groups."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table
from rich import text as rich_text

from pauldot import apply as pauldot_apply
from pauldot import config, git, profiles, shell, state, tools, zshrc

app = typer.Typer(no_args_is_help=True)
profile_app = typer.Typer()
tool_app = typer.Typer()
keys_app = typer.Typer()
secret_app = typer.Typer()
help_app = typer.Typer()

app.add_typer(profile_app, name="profile")
app.add_typer(tool_app, name="tool", help="Manage tools installed on the system.")
app.add_typer(keys_app, name="keys")
app.add_typer(secret_app, name="secret")
app.add_typer(help_app, name="help")

console = rich_console.Console()

_ZSHRC_ACTION_LABELS: dict[str, rich_text.Text] = {
    "created": rich_text.Text("✓ created", style="green"),
    "backup_replaced": rich_text.Text("✓ replaced", style="green"),
    "replaced": rich_text.Text("✓ replaced", style="green"),
    "no_op": rich_text.Text("✓ already linked", style="dim"),
}

_TOOL_ACTION_LABELS: dict[str, tuple[str, str]] = {
    "installed": ("✓ installed", "green"),
    "already_installed": ("✓ already installed", "dim"),
    "skipped": ("– skipped", "dim"),
    "failed": ("⚠ failed", "yellow"),
}


def _print_zshrc_result(result: zshrc.ZshrcResult, dry_run: bool) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    action = _ZSHRC_ACTION_LABELS[result.action]
    if dry_run:
        action = action + rich_text.Text(" (dry run)", style="dim")

    t.add_row(rich_text.Text("~/.zshrc", style="bold"), action)
    t.add_row(rich_text.Text("  → target", style="dim"), rich_text.Text(str(result.target)))
    if result.backup:
        t.add_row(rich_text.Text("  → backup", style="dim"), rich_text.Text(str(result.backup)))

    console.print(t)


def _print_tool_results(tool_results: list[tools.ToolResult]) -> None:
    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    for result in tool_results:
        label, style = _TOOL_ACTION_LABELS[result.action]
        error_text = rich_text.Text(result.error or "", style="dim")
        t.add_row(rich_text.Text(result.name), rich_text.Text(label, style=style), error_text)
        if result.output:
            for line in result.output.splitlines():
                t.add_row(rich_text.Text(""), rich_text.Text(f"  {line}", style="dim"), rich_text.Text(""))

    console.print(t)


def _print_apply_result(result: pauldot_apply.ApplyResult, dry_run: bool) -> None:
    _print_zshrc_result(result.zshrc, dry_run)
    if result.tools:
        _print_tool_results(result.tools)


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
def apply(
    verbose: typing.Annotated[
        bool, typer.Option("--verbose", "-v", help="Show subprocess output from tool installs.")
    ] = False,
) -> None:
    """Reconcile current profile: symlink ~/.zshrc, install missing tools."""
    try:
        result = pauldot_apply.run(pathlib.Path.home(), verbose=verbose)
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


# — tool subcommands ———————————————————————————————————————————————————————————


@tool_app.command("list")
def tool_list() -> None:
    """List all tools defined in tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    all_tools = config.load_tools(repo_path)

    if not all_tools:
        console.print("No tools defined. Run `pauldot tool add` to add one.")
        return

    try:
        active_profile = profiles.resolve(repo_path, state.load_state().active_profile)
        profile_tools = set(active_profile.tools)
    except FileNotFoundError:
        profile_tools = set()

    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)
    t.add_column(no_wrap=True)

    for tool_def in all_tools:
        is_installed = tools.check(tool_def)
        status_text = rich_text.Text(
            "✓ installed" if is_installed else "✗ not installed",
            style="green" if is_installed else "red",
        )
        profile_marker = rich_text.Text(
            " (active profile)" if tool_def.name in profile_tools else "",
            style="dim",
        )
        t.add_row(rich_text.Text(tool_def.name), status_text, profile_marker)

    console.print(t)


@tool_app.command("install")
def tool_install(
    name: typing.Annotated[str | None, typer.Argument()] = None,
    verbose: typing.Annotated[
        bool, typer.Option("--verbose", "-v", help="Show subprocess output from install commands.")
    ] = False,
) -> None:
    """Install a specific tool, or all tools in the active profile."""
    repo_path = pathlib.Path.home() / ".pauldot"
    all_tools = {t.name: t for t in config.load_tools(repo_path)}
    os_name = shell.detect_os()

    if name is not None:
        if name not in all_tools:
            console.print(f"[red]Error:[/red] Tool '{name}' not found. Run `pauldot tool list`.")
            raise typer.Exit(1)
        tool_names = [name]
    else:
        try:
            active = state.load_state().active_profile
            profile = profiles.resolve(repo_path, active)
            tool_names = profile.tools
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from None

    results = tools.reconcile(tool_names, all_tools, os_name, verbose=verbose)
    _print_tool_results(results)


@tool_app.command("add")
def tool_add() -> None:
    """Interactively add a tool definition to tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"

    name = typer.prompt("Tool name")
    check_cmd = typer.prompt("Check command (e.g. command -v uv)")
    macos_install = typer.prompt("macOS install command (leave blank to skip)", default="")
    linux_install = typer.prompt("Linux install command (leave blank to skip)", default="")

    existing = config.load_tools(repo_path)
    if any(t.name == name for t in existing):
        console.print(f"[yellow]⚠[/yellow] Tool '{name}' already defined. Edit tools/tools.toml to update it.")
        raise typer.Exit(1)

    new_tool = config.ToolDefinition(
        name=name,
        check=check_cmd,
        install=config.ToolInstall(
            macos=macos_install or None,
            linux=linux_install or None,
        ),
    )
    config.save_tools(repo_path, [*existing, new_tool])
    console.print(f"✓ Added '{name}' to tools/tools.toml.")


@tool_app.command("remove")
def tool_remove(name: str) -> None:
    """Remove a tool definition from tools/tools.toml."""
    repo_path = pathlib.Path.home() / ".pauldot"
    existing = config.load_tools(repo_path)
    updated = [t for t in existing if t.name != name]

    if len(updated) == len(existing):
        console.print(f"[red]Error:[/red] Tool '{name}' not found. Run `pauldot tool list`.")
        raise typer.Exit(1)

    config.save_tools(repo_path, updated)
    console.print(f"✓ Removed '{name}' from tools/tools.toml.")
