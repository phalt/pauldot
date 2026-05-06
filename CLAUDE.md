# CLAUDE.md

## Project Overview

Pauldot (`pauldot`) is a personal system manager: a CLI tool that manages dotfiles, profiles, and tool installations across machines from a single git repo. See `spec.md` for the full specification.

## Reference Project

All structural decisions (layout, tooling, conventions) follow [phalt/paulblish](https://github.com/phalt/paulblish). When in doubt about "how should this be structured?" — do it the way paulblish does it.

## Project Conventions

- **Package layout:** Flat layout with `pauldot/` at repo root (not `src/`).
- **Dependency management:** `uv` for everything. `uv.lock` committed. `.python-version` pinning Python version.
- **Python version:** 3.14. No code targeting older versions.
- **Build backend:** `hatchling` in `pyproject.toml`.
- **CLI framework:** `typer` for the command surface. Subcommands grouped via `typer.Typer()` instances (`profile`, `tool`, `alias`, `help`).
- **Linting/formatting:** `ruff` configured in `pyproject.toml` under `[tool.ruff]`. Line length 120, target Python 3.14.
- **Tests:** `pytest` in `tests/` at repo root. Fixtures in `tests/fixtures/`. Filesystem-touching tests use `tmp_path` and a fake `$HOME` fixture — never the real home directory.
- **Makefile:** `make install`, `make test`, `make lint`, `make format`, `make clean`.

## Key Rules

- **Use pydantic for all structured data.** Prefer `pydantic.BaseModel` over `dataclasses.dataclass` everywhere. `pydantic` is installed; use it.

- **Import everything as a module; never destructure it.** For example: Always `import typing` and reference names as `typing.Literal`, `typing.Any`, etc. Never `from typing import Literal`. Another example: Always `from pauldot import zshrc` and reference names as `zshrc.apply_zshrc`, never `from pauldot.zshrc import apply_zshrc`.

- **All imports must be at the top of the file.** No inline imports inside functions or methods under any circumstances.

- **Every implementation change must include tests.** Before marking a phase step as done, either confirm existing test coverage is sufficient and adapt it, or write new tests. No untested code gets checked off.

- **`apply` must never touch the real `$HOME` in tests.** Always use the fake-home fixture. The cost of a bug here is a clobbered `~/.zshrc`.

- **The dotfiles repo URL is never hardcoded in the codebase.** It lives in local state (`~/.config/pauldot/state.toml`), set by `pauldot init`. Anyone forking pauldot points it at their own repo via `init`.

- **`pauldot.toml` is the only place that committed config lives.** Local state (`state.toml`) is per-machine and never enters git.

- **Apply is idempotent.** Running it ten times produces the same result as running it once. No "uninstall" semantics for tools.

- **Tool install failures don't abort the apply loop.** Each failure is reported in the summary; the loop continues.

- **OS detection is centralised in `shell.py`.** Two values only: `macos` or `linux`. No code branches on `platform.system()` directly anywhere else.

- **Symlink, don't source.** `~/.zshrc` is a symlink to the generated file. Existing non-symlink `~/.zshrc` is backed up to `~/.zshrc.bak.<timestamp>` before being replaced.

- **`gh` is shelled out.** `gh.py` wraps it; `pauldot help gh` is the user-facing walkthrough.

- **`apply` and `sync` are separate verbs.** Apply is deterministic from local state. Sync handles git pull/push. Never combine them.

- **CLI output uses `rich`.** Tables for summaries, prompts via `rich.prompt`. No bare `print` in user-facing output.

## Development Commands

```
make install        # uv sync
make test           # uv run pytest
make lint           # uv run ruff check .
make format         # uv run ruff format .
make clean          # rm -rf __pycache__ + egg-info + .pytest_cache
uv run pauldot apply           # reconcile current profile (uses real $HOME — be careful)
uv run pauldot status          # dry-run apply, no side effects
```

## Implementation Progress

Current phase: **Phase 0.6**

After completing each phase action, check it off in `spec.md` (change `- [ ]` to `- [x]`) and update the current phase note here if the phase changes.

Phases (see `spec.md` for full detail):

- Phase 0.1 — single profile, hardcoded path, symlink + backup
- Phase 0.2 — TOML config, profiles, `pauldot init`
- Phase 0.3 — tool reconciliation
- Phase 0.4 — quality of life (alias add, doctor, sync, help commands)
- Phase 0.5 — ~~encryption (age, keys, secrets)~~ — skipped, out of scope
- Phase 0.6 — fork-friendliness (`init --scaffold`, distribution, README)

## Architecture

Apply pipeline sequence: load state → load `pauldot.toml` → resolve profile + extends → detect OS → generate zshrc → backup + symlink → reconcile tools → print summary.

Key modules:

- `cli.py` — typer app, command definitions, subcommand groups
- `config.py` — pydantic models, loading `pauldot.toml` + profiles
- `state.py` — `~/.config/pauldot/state.toml` read/write
- `apply.py` — the reconciliation engine
- `profiles.py` — profile resolution, `extends` chain
- `tools.py` — tool check + install logic, OS-specific dispatch
- `zshrc.py` — generation of `.zshrc.generated`, symlink + backup
- `git.py` — subprocess wrappers for `git`
- `gh.py` — subprocess wrappers for `gh`, auth detection
- `shell.py` — subprocess wrappers, OS detection (`macos` | `linux`)
- `scaffold.py` — `init --scaffold` (generates a starter dotfiles repo from `templates/scaffold/`)
- `help_text.py` — content for `pauldot help bootstrap`, `help gh`, `help fork`

## Personal Preferences

- **Casual but precise.** Comments and CLI strings can be playful; module/function docstrings are direct and factual.
- **No premature abstractions.** If a thing is used once, inline it. Extract on the second use, not the first.
- **Errors are loud and useful.** Every `raise` or `typer.Exit(1)` is paired with a clear message that says what went wrong, what the user can do, and (if relevant) which command to run next.
- **No emoji in code or commits.** `rich` symbols (`✓`, `⚠`, `→`) are fine in CLI output.
- **No Elon Musk references in any examples or copy.** Use other names where an example owner is needed.
