"""Alias subcommands: add, remove, list."""

import pathlib
import typing

import typer
from rich import console as rich_console
from rich import table as rich_table

from pauldot import apply as pauldot_apply
from pauldot import config, display, git, state

alias_app = typer.Typer()

console = rich_console.Console()

_ALIAS_PREFIX = "alias "


def _aliases_file(repo_path: pathlib.Path) -> pathlib.Path:
    return repo_path / "files" / "aliases.zsh"


def _profile_aliases_file(repo_path: pathlib.Path, profile_name: str) -> pathlib.Path:
    return repo_path / "files" / f"aliases.{profile_name}.zsh"


def _remove_alias_from_file(path: pathlib.Path, key: str) -> bool:
    """Remove alias <key> from file. Returns True if the alias was found and removed."""
    if not path.exists():
        return False
    lines = path.read_text().splitlines(keepends=True)
    new_lines = [line for line in lines if not line.strip().startswith(f"{_ALIAS_PREFIX}{key}=")]
    if len(new_lines) == len(lines):
        return False
    # Collapse consecutive blank lines left by the removal
    result: list[str] = []
    prev_blank = False
    for line in new_lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    path.write_text("".join(result))
    return True


def _read_aliases_from_file(path: pathlib.Path) -> list[tuple[str, str]]:
    """Return list of (key, value) pairs parsed from an aliases file."""
    if not path.exists():
        return []
    pairs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith(_ALIAS_PREFIX):
            continue
        rest = line[len(_ALIAS_PREFIX) :]
        if "=" not in rest:
            continue
        key, _, value = rest.partition("=")
        value = value.strip("\"'")
        pairs.append((key.strip(), value))
    return pairs


@alias_app.command("add")
def alias_add(
    key: str,
    value: str,
    profile_name: typing.Annotated[
        str | None,
        typer.Option("--profile", help="Write alias to a profile-specific aliases file instead of shared."),
    ] = None,
) -> None:
    """Add an alias to files/aliases.zsh (or a profile-specific aliases file)."""
    repo_path = pathlib.Path.home() / ".pauldot"

    if profile_name is not None:
        target_file = _profile_aliases_file(repo_path, profile_name)
        if not target_file.exists():
            target_file.write_text(f"# Aliases for {profile_name} profile.\n")
    else:
        target_file = _aliases_file(repo_path)
        if not target_file.exists():
            console.print(f"[red]Error:[/red] {target_file} not found. Run `pauldot apply` first.")
            raise typer.Exit(1)

    existing_keys = {k for k, _ in _read_aliases_from_file(target_file)}
    if key in existing_keys:
        console.print(
            f"[yellow]⚠[/yellow] Alias '{key}' already exists in {target_file.name}. Edit it directly to update."
        )
        raise typer.Exit(1)

    with target_file.open("a") as f:
        f.write(f'\nalias {key}="{value}"\n')

    console.print(f'✓ Added alias {key}="{value}"')

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: add alias {key}")
            console.print("✓ Committed to dotfiles repo.")
    except (FileNotFoundError, RuntimeError):
        pass  # auto-commit is best-effort

    try:
        result = pauldot_apply.run(pathlib.Path.home())
        display.print_zshrc_result(result.zshrc, dry_run=False)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[yellow]⚠[/yellow] Apply failed after alias add: {e}")


@alias_app.command("remove")
def alias_remove(
    key: str,
    profile_name: typing.Annotated[
        str | None,
        typer.Option("--profile", help="Remove alias from a specific profile's aliases file."),
    ] = None,
) -> None:
    """Remove an alias from aliases files."""
    repo_path = pathlib.Path.home() / ".pauldot"

    if profile_name is not None:
        target_file = _profile_aliases_file(repo_path, profile_name)
        removed = _remove_alias_from_file(target_file, key)
        if not removed:
            console.print(f"[red]Error:[/red] Alias '{key}' not found in {target_file.name}.")
            raise typer.Exit(1)
        sources = [target_file.name]
    else:
        # Auto-detect: check shared file and active profile file.
        shared_file = _aliases_file(repo_path)
        removed_shared = _remove_alias_from_file(shared_file, key)

        active_profile_file: pathlib.Path | None = None
        removed_profile = False
        try:
            active = state.load_state().active_profile
            active_profile_file = _profile_aliases_file(repo_path, active)
            removed_profile = _remove_alias_from_file(active_profile_file, key)
        except FileNotFoundError:
            pass

        if not removed_shared and not removed_profile:
            console.print(f"[red]Error:[/red] Alias '{key}' not found. Run `pauldot alias list` to see defined aliases.")
            raise typer.Exit(1)

        sources = []
        if removed_shared:
            sources.append(shared_file.name)
        if removed_profile and active_profile_file:
            sources.append(active_profile_file.name)

    console.print(f"✓ Removed alias '{key}' from {', '.join(sources)}")

    try:
        cfg = config.load_pauldot_config(repo_path)
        if cfg.git.auto_commit:
            git.commit(repo_path, f"pauldot: remove alias {key}")
            console.print("✓ Committed to dotfiles repo.")
    except (FileNotFoundError, RuntimeError):
        pass  # auto-commit is best-effort

    try:
        result = pauldot_apply.run(pathlib.Path.home())
        display.print_zshrc_result(result.zshrc, dry_run=False)
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[yellow]⚠[/yellow] Apply failed after alias remove: {e}")


@alias_app.command("list")
def alias_list() -> None:
    """List aliases defined in aliases files."""
    repo_path = pathlib.Path.home() / ".pauldot"

    try:
        active = state.load_state().active_profile
    except FileNotFoundError:
        active = None

    shared_pairs = [(k, v, "shared") for k, v in _read_aliases_from_file(_aliases_file(repo_path))]
    profile_pairs: list[tuple[str, str, str]] = []
    if active:
        pf = _profile_aliases_file(repo_path, active)
        profile_pairs = [(k, v, active) for k, v in _read_aliases_from_file(pf)]

    all_pairs = shared_pairs + profile_pairs

    if not all_pairs:
        console.print("No aliases defined. Run `pauldot alias add <key> <value>` to add one.")
        return

    t = rich_table.Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("Alias", style="bold", no_wrap=True)
    t.add_column("Command", no_wrap=True)
    t.add_column("Source", style="dim", no_wrap=True)
    for key, value, source in all_pairs:
        t.add_row(key, value, source)
    console.print(t)
