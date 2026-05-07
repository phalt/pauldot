"""Absorbs external modifications to .zshrc.generated back into source files."""

import pathlib

import pydantic

from pauldot import profiles, state, zshrc


class AbsorbResult(pydantic.BaseModel):
    lines: list[str]
    target: pathlib.Path | None
    dry_run: bool


def absorb(
    home: pathlib.Path,
    repo_path: pathlib.Path,
    target_name: str = "zshrc.base",
    dry_run: bool = False,
) -> AbsorbResult:
    """Diff .zshrc.generated against what pauldot would generate and absorb the extra lines.

    Extra lines (written by external tools) are appended to target_name inside files/.
    In dry_run mode nothing is written; the result still describes what would be absorbed.

    Raises FileNotFoundError if .zshrc.generated does not exist.
    Raises ValueError if the active profile cannot be resolved.
    """
    generated_path = repo_path / zshrc.GENERATED_ZSHRC_REL

    if not generated_path.exists():
        raise FileNotFoundError(f"{generated_path} not found. Run `pauldot apply` first.")

    current_state = state.load_state()
    profile = profiles.resolve(repo_path, current_state.active_profile)

    actual = generated_path.read_text()
    expected = zshrc.expected_content(repo_path, profile)
    extra = _extra_lines(actual, expected)

    if not extra or dry_run:
        return AbsorbResult(lines=extra, target=None, dry_run=dry_run)

    target = repo_path / "files" / target_name
    with target.open("a") as f:
        f.write("\n# Absorbed by pauldot absorb\n")
        for line in extra:
            f.write(line + "\n")

    return AbsorbResult(lines=extra, target=target, dry_run=dry_run)


def _extra_lines(actual: str, expected: str) -> list[str]:
    """Return lines present in actual but not in expected, preserving order.

    Tries a prefix match first (the common case: tools append to the end).
    Falls back to a set-diff for cases where the generated file was modified mid-file.
    Blank lines are excluded from the result.
    """
    expected_stripped = expected.rstrip()
    actual_stripped = actual.rstrip()

    if actual_stripped.startswith(expected_stripped):
        remainder = actual_stripped[len(expected_stripped) :]
        return [line for line in remainder.splitlines() if line.strip()]

    # Fallback: set diff preserving order.
    expected_lines = set(expected.splitlines())
    return [line for line in actual.splitlines() if line not in expected_lines and line.strip()]
