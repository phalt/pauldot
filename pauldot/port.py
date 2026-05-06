"""Ports an existing ~/.zshrc into a freshly scaffolded dotfiles repo."""

import pathlib

import pydantic


class PortResult(pydantic.BaseModel):
    aliases_added: list[str]
    aliases_skipped: list[str]
    zshrc_line_count: int


def port(home: pathlib.Path, repo_path: pathlib.Path) -> PortResult:
    """Read ~/.zshrc and distribute its content into the scaffolded repo.

    Alias lines go to files/aliases.zsh; everything else to files/zshrc.base.
    Raises FileNotFoundError if ~/.zshrc does not exist.
    Raises ValueError if ~/.zshrc is already a symlink (already managed).
    """
    zshrc = home / ".zshrc"

    if not zshrc.exists():
        raise FileNotFoundError("No ~/.zshrc found to port.")
    if zshrc.is_symlink():
        raise ValueError("~/.zshrc is already a symlink — nothing to port.")

    alias_lines, other_lines = _split(zshrc.read_text())

    aliases_file = repo_path / "files" / "aliases.zsh"
    added, skipped = _port_aliases(alias_lines, aliases_file)
    _port_zshrc_base(other_lines, repo_path / "files" / "zshrc.base")

    return PortResult(
        aliases_added=added,
        aliases_skipped=skipped,
        zshrc_line_count=len(other_lines),
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
    rest = line[len("alias "):]
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


def _port_aliases(alias_lines: list[str], aliases_file: pathlib.Path) -> tuple[list[str], list[str]]:
    existing_keys = _existing_alias_keys(aliases_file)
    added = [line for line in alias_lines if _alias_key(line) not in existing_keys]
    skipped = [line for line in alias_lines if _alias_key(line) in existing_keys]

    if added:
        with aliases_file.open("a") as f:
            f.write("\n# Ported from existing ~/.zshrc\n")
            for line in added:
                f.write(line + "\n")

    return added, skipped


def _port_zshrc_base(lines: list[str], base_zshrc: pathlib.Path) -> None:
    content = "\n".join(lines).strip()
    if content:
        base_zshrc.write_text(content + "\n")
