"""Alias subcommands: add, list."""

import pathlib

import typer
from rich import console as rich_console
from rich import table as rich_table

from pauldot import config, git

alias_app = typer.Typer()

console = rich_console.Console()

_ALIAS_PREFIX = "alias "


def _aliases_file(repo_path: pathlib.Path) -> pathlib.Path:
    return repo_path / "files" / "aliases.zsh"


def _read_aliases(repo_path: pathlib.Path) -> list[tuple[str, str]]:
    """Return list of (key, value) pairs parsed from aliases.zsh."""
    path = _aliases_file(repo_path)
    if not path.exists():
        return []
    pairs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith(_ALIAS_PREFIX):
            continue
        # alias key="value" or alias key='value'
        rest = line[len(_ALIAS_PREFIX) :]
        if "=" not in rest:
            continue
        key, _, value = rest.partition("=")
        value = value.strip("\"'")
        pairs.append((key.strip(), value))
    return pairs


@alias_app.command("add")
def alias_add(key: str, value: str) -> None:
    """Add an alias to files/aliases.zsh."""
    repo_path = pathlib.Path.home() / ".pauldot"
    aliases_file = _aliases_file(repo_path)

    if not aliases_file.exists():
        console.print(f"[red]Error:[/red] {aliases_file} not found. Run `pauldot apply` first.")
        raise typer.Exit(1)

    existing_keys = {k for k, _ in _read_aliases(repo_path)}
    if key in existing_keys:
        console.print(f"[yellow]⚠[/yellow] Alias '{key}' already exists. Edit files/aliases.zsh to update it.")
        raise typer.Exit(1)

    with aliases_file.open("a") as f:
        f.write(f'\nalias {key}="{value}"\n')

    console.print(f'✓ Added alias {key}="{value}"')

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: add alias {key}")
            console.print("✓ Committed to dotfiles repo.")
    except FileNotFoundError, RuntimeError:
        pass  # auto-commit is best-effort


@alias_app.command("list")
def alias_list() -> None:
    """List aliases defined in files/aliases.zsh."""
    repo_path = pathlib.Path.home() / ".pauldot"
    pairs = _read_aliases(repo_path)

    if not pairs:
        console.print("No aliases defined. Run `pauldot alias add <key> <value>` to add one.")
        return

    t = rich_table.Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold", no_wrap=True)
    t.add_column(no_wrap=True)
    for key, value in pairs:
        t.add_row(key, value)
    console.print(t)
