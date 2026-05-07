"""Migrates an existing ~/.zshrc into a pauldot-managed dotfiles repo."""

import pathlib

import pydantic


class MigrateResult(pydantic.BaseModel):
    aliases_added: list[str]
    aliases_skipped: list[str]
    zshrc_line_count: int
    dry_run: bool


def migrate(home: pathlib.Path, repo_path: pathlib.Path, dry_run: bool = False) -> MigrateResult:
    """Read ~/.zshrc and distribute its content into the repo.

    Alias lines go to files/aliases.zsh; everything else to files/zshrc.base.
    In dry_run mode nothing is written; the result still describes what would change.

    Raises FileNotFoundError if ~/.zshrc does not exist.
    Raises ValueError if ~/.zshrc is already a symlink (already managed by pauldot).
    """
    zshrc = home / ".zshrc"

    if not zshrc.exists():
        raise FileNotFoundError("No ~/.zshrc found to migrate.")
    if zshrc.is_symlink():
        raise ValueError("~/.zshrc is already a symlink — pauldot is already managing it.")

    alias_lines, other_lines = _split(zshrc.read_text())

    aliases_file = repo_path / "files" / "aliases.zsh"
    existing_keys = _existing_alias_keys(aliases_file)
    aliases_added = [line for line in alias_lines if _alias_key(line) not in existing_keys]
    aliases_skipped = [line for line in alias_lines if _alias_key(line) in existing_keys]

    if not dry_run:
        if aliases_added:
            with aliases_file.open("a") as f:
                f.write("\n# Migrated from existing ~/.zshrc\n")
                for line in aliases_added:
                    f.write(line + "\n")
        _write_zshrc_base(other_lines, repo_path / "files" / "zshrc.base")

    return MigrateResult(
        aliases_added=aliases_added,
        aliases_skipped=aliases_skipped,
        zshrc_line_count=len(other_lines),
        dry_run=dry_run,
    )


def _split(content: str) -> tuple[list[str], list[str]]:
    """Partition lines into (alias_lines, other_lines)."""
    alias_lines = []
    other_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("alias ") and "=" in stripped:
            alias_lines.append(stripped)
        else:
            other_lines.append(line)
    return alias_lines, other_lines


def _alias_key(line: str) -> str:
    """Extract the key from a line like 'alias foo="bar"'."""
    rest = line[len("alias ") :]
    key, _, _ = rest.partition("=")
    return key.strip()


def _existing_alias_keys(aliases_file: pathlib.Path) -> set[str]:
    if not aliases_file.exists():
        return set()
    return {
        _alias_key(line.strip())
        for line in aliases_file.read_text().splitlines()
        if line.strip().startswith("alias ") and "=" in line
    }


def _write_zshrc_base(lines: list[str], base_zshrc: pathlib.Path) -> None:
    content = "\n".join(lines).strip()
    if content:
        base_zshrc.write_text(content + "\n")
