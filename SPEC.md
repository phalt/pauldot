# pauldot — Specification

A personal system manager: dotfiles, profiles, and tool installations across machines. File-first, written in Python, fork-friendly.

## Goals

- Manage `.zshrc` (and other dotfiles) across multiple machines from a single git repo
- Layer machine-specific profiles (work, personal) on top of a shared base
- Declare desired tools and their install commands; reconcile on apply
- Quick CLI affordances for the daily case (adding aliases, switching profiles)
- One-line bootstrap on a fresh machine
- Be forkable: the tool ships with no embedded assumptions about whose dotfiles repo it points at

## Non-goals

- Not a general-purpose config manager (no Ansible/Nix ambitions)
- Not cross-shell — zsh only
- No GUI, no daemon, no background sync
- No secrets management or encryption

## Tech stack

- **Python 3.14**, packaged with `uv`. All project commands use `uv` (`uv run`, `uv sync`, `uv tool install`, `uv build`, etc.) — no bare `python` or `pip`.
- **`typer`** for the CLI
- **`tomllib`** (stdlib) for reading TOML, **`tomli-w`** for writing
- **`pydantic`** for config schema validation
- **`rich`** for output
- **`platformdirs`** for cross-platform paths
- Shell out to `git` and `gh` via `subprocess`

Everything else is stdlib. No async. No database.

## Two repos, distinct concerns

This matters for the fork story:

1. **`pauldot`** (this codebase) — the CLI tool. Forkable, but most users won't need to.
2. **`<your>-dotfiles`** (the user's repo) — their actual config.

The CLI never hardcodes a dotfiles repo URL. The user's repo URL lives in their local `~/.config/pauldot/state.toml`, set during bootstrap or `pauldot init`.

## Repo layout (the dotfiles repo)

```
~/.pauldot/                       # cloned dotfiles repo
├── pauldot.toml                  # top-level config (committed)
├── profiles/
│   ├── base.toml
│   ├── work.toml
│   └── personal.toml
├── files/
│   ├── zshrc.base
│   ├── zshrc.work
│   ├── zshrc.personal
│   ├── aliases.zsh
│   └── home/                     # tracked dotfiles (optional)
│       ├── .gitconfig
│       └── .config/
│           └── starship.toml
├── tools/
│   └── tools.toml
└── bootstrap.sh
```

## Local state (not in git)

```
~/.config/pauldot/
└── state.toml                    # active profile, dotfiles repo URL, last apply
```

`state.toml` is the only thing that changes per-machine. Losing it means re-running `pauldot init <repo-url>` and selecting a profile.

## Config schemas

### `pauldot.toml`

Committed to the dotfiles repo. The fork-and-customise file.

```toml
[core]
default_profile = "personal"
shell = "zsh"

[git]
# The dotfiles repo URL is stored in local state, not here. But everything else
# about how pauldot interacts with git lives here.
auto_commit = true
auto_push = false
default_branch = "main"
visibility = "private"            # "private" | "public"; affects bootstrap messaging

[bootstrap]
require_gh_auth = true            # private repo → must auth via gh first
```

`visibility` drives what `pauldot doctor` and `pauldot help bootstrap` say, and what the bootstrap script checks before cloning.

### `profiles/<name>.toml`

```toml
extends = "base"

zshrc = "files/zshrc.work"

tools = ["starship", "zed", "uv", "obsidian", "ripgrep"]

dotfiles = [".gitconfig", ".config/starship.toml"]

[env]
WORK_MODE = "true"
EDITOR = "zed --wait"
```

Single-level extends only — `work` extends `base`, no chains.

`dotfiles` lists paths relative to `~`. Each entry maps to a file under `files/home/` in the repo. On `apply`, missing files are copied to `~`; existing files are left alone unless `--overwrite` is passed. `env` variables are exported inline into `~/.zshrc` on apply.

### `tools/tools.toml`

```toml
[[tool]]
name = "uv"
check = "command -v uv"
install.macos = "curl -LsSf https://astral.sh/uv/install.sh | sh"
install.linux = "curl -LsSf https://astral.sh/uv/install.sh | sh"

[[tool]]
name = "starship"
check = "command -v starship"
install.macos = "brew install starship"
install.linux = "curl -sS https://starship.rs/install.sh | sh -s -- -y"

[[tool]]
name = "zed"
check = "command -v zed"
install.macos = "brew install --cask zed"
install.linux = "curl -f https://zed.dev/install.sh | sh"

[[tool]]
name = "obsidian"
check = "test -d /Applications/Obsidian.app"
install.macos = "brew install --cask obsidian"
# no linux entry — silently skipped on linux
```

## CLI surface

```
pauldot init [<repo-url>]            # interactive if no URL; sets local state
pauldot init --scaffold <path>       # generates an empty dotfiles repo structure
pauldot apply                        # reconcile current profile
pauldot status                       # dry-run apply
pauldot doctor                       # health check

pauldot profile show
pauldot profile set <name>
pauldot profile list

pauldot tool add                     # interactive
pauldot tool list
pauldot tool install [<name>]
pauldot tool remove <name>

pauldot alias add <key> <value>
pauldot alias list

pauldot sync                         # git pull --rebase, then push if local commits

pauldot help bootstrap               # bootstrap walkthrough
pauldot help fork                    # how to fork & customise
pauldot help gh                      # gh auth walkthrough

pauldot absorb                       # absorb external modifications to ~/.zshrc back into source files
pauldot track <path>                 # copy a dotfile into the repo and add it to the active profile

pauldot edit [profile|tools|zshrc|pauldot]
```

## How `pauldot init` works

Two paths, depending on whether `gh` is authenticated:

**Path A — fresh machine, no gh auth, private repo:**

```
$ pauldot init
No dotfiles repo configured.

Is your dotfiles repo private? [Y/n]: y

Private repos require GitHub CLI authentication. Run:

    pauldot help gh

…then re-run `pauldot init <repo-url>`.
```

**Path B — repo URL provided:**

```
$ pauldot init git@github.com:paul/dotfiles
Cloning into ~/.pauldot...
Repo cloned. Found pauldot.toml.

Available profiles: base, work, personal
Default: personal

Set active profile [personal]: work
Active profile: work

Run `pauldot apply` when ready.
```

`pauldot init` is the only command that writes the dotfiles repo URL into `state.toml`. There's no flag to set it elsewhere — keeps the bootstrap path explicit.

## How `apply` works

1. Load `state.toml`; resolve active profile
2. Load `pauldot.toml` from the repo
3. Resolve profile + extends chain
4. Detect OS (`shell.py` → `macos` or `linux`)
5. **zshrc reconciliation:**
   - Concatenate source files (base, profile, aliases) and export `env` vars inline
   - Back up any existing non-pauldot `~/.zshrc` to `~/.zshrc.bak.<timestamp>`
   - Write the result directly to `~/.zshrc` as a plain file (detected by `PAULDOT_HEADER` on line 1)
6. **Dotfile reconciliation:**
   - For each path in the active profile's `dotfiles` list: copy from `files/home/<path>` to `~/<path>` if missing
   - With `--overwrite`: copy regardless, backing up the existing file first
7. **Tool reconciliation:**
   - For each tool in the resolved profile: run check, install if missing
   - Skip tools with no install entry for the current OS
   - Failures are reported, don't abort the loop
8. Print a summary table

## How `bootstrap.sh` works

Lives in the user's dotfiles repo. Each user has their own copy via fork or scaffold, but the script itself is generic — it reads `pauldot.toml` once cloned to decide what to do.

```sh
#!/usr/bin/env sh
set -e

REPO_URL="${PAULDOT_REPO:-}"

cat <<'EOF'
pauldot bootstrap
─────────────────
This will:
  1. Install uv (if missing)
  2. Install pauldot via uv
  3. Clone your dotfiles repo
  4. Run pauldot apply

If your dotfiles repo is PRIVATE, you'll need GitHub CLI authentication.
After this script installs pauldot, run:

    pauldot help gh

…to walk through gh setup before re-running this script with PAULDOT_REPO set.

EOF

if [ -z "$REPO_URL" ]; then
  printf "Dotfiles repo URL (or Ctrl-C to abort and run 'pauldot help gh' first): "
  read -r REPO_URL
fi

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
  echo "→ Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2. pauldot
echo "→ Installing pauldot"
uv tool install pauldot

# 3. clone & init
echo "→ Initialising dotfiles"
pauldot init "$REPO_URL"

# 4. apply
echo "→ Applying"
pauldot apply

echo "✓ Done. Open a new shell or run 'source ~/.zshrc'."
```

The user runs:

```sh
curl -sSL https://raw.githubusercontent.com/<their-fork>/dotfiles/main/bootstrap.sh | sh
```

…or, with the repo pre-set:

```sh
PAULDOT_REPO=git@github.com:paul/dotfiles curl -sSL ... | sh
```

If the repo is private, the user runs `pauldot help gh` first (which doesn't need the repo cloned — just `pauldot` installed).

## `pauldot help gh` output

A first-class command because this is the single biggest setup hurdle.

```
GitHub CLI setup for private dotfiles
─────────────────────────────────────

1. Install gh:
     macOS:  brew install gh
     Linux:  see https://github.com/cli/cli#installation

2. Authenticate:
     gh auth login

   When prompted:
     • Account:        GitHub.com
     • Protocol:       SSH (recommended) or HTTPS
     • SSH key:        upload an existing key, or let gh generate one
     • Auth method:    web browser (easiest)

3. Verify:
     gh auth status

4. Configure git to use gh's credentials:
     gh auth setup-git

5. Re-run bootstrap or pauldot init:
     pauldot init git@github.com:<you>/dotfiles
```

## `pauldot help fork` output

For someone who finds pauldot and wants to use it for their own dotfiles:

```
Setting up your own dotfiles with pauldot
─────────────────────────────────────────

You don't fork pauldot itself — you make your own dotfiles repo.
pauldot is the engine; the dotfiles repo is your config.

1. Create a new repo (private recommended):
     gh repo create <you>/dotfiles --private --clone

2. Scaffold the structure:
     pauldot init --scaffold ./dotfiles

   This creates:
     pauldot.toml, profiles/, files/, tools/, bootstrap.sh

3. Edit pauldot.toml — set core.default_profile, git.visibility, etc.

4. Edit bootstrap.sh — change the PAULDOT_REPO default to your repo URL.

5. Commit and push:
     cd dotfiles && git add . && git commit -m "init" && git push

6. On other machines:
     curl -sSL https://raw.githubusercontent.com/<you>/dotfiles/main/bootstrap.sh | sh

That's it. pauldot itself is unchanged — you just point it at your repo.
```

## How `pauldot absorb` works

The problem: When external tools (nvm, pyenv, brew, etc.) install themselves they append to `~/.zshrc`. The next `pauldot apply` regenerates `~/.zshrc` from source, silently wiping those additions.

`pauldot absorb` recovers those additions and commits them back into the source files.

**Steps:**

1. Read `~/.zshrc` (the live, possibly-modified file)
2. Reconstruct what pauldot would generate from the current source files (without writing anything)
3. Diff: lines in the live file that are not in the reconstructed output = external additions
4. Append those lines to the target source file (default: `files/zshrc.base`)
5. If `git.auto_commit = true`, commit the change

**Flags:**

```
pauldot absorb                     # absorb into zshrc.base (default)
pauldot absorb --target zshrc.work # absorb into a specific source file
pauldot absorb --dry-run           # print what would be absorbed without writing
```

**Behaviour:**

- If `~/.zshrc` is not managed by pauldot (no `PAULDOT_HEADER`), exits with a clear error
- If there are no external additions, prints "Nothing to absorb." and exits cleanly
- Strips blank lines and comment-only blocks from the diff before appending to keep source files clean
- Never modifies `~/.zshrc` directly — only the source files
- The diff is line-order-preserving: additions appear in the order they were appended by tools

**Example session:**

```
$ nvm install --lts
# nvm appends to ~/.zshrc

$ pauldot absorb --dry-run
Would append 3 lines to files/zshrc.base:

  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

$ pauldot absorb
✓ Absorbed 3 lines into files/zshrc.base
✓ Committed to dotfiles repo.
```

## How `~/.zshrc` is generated

`~/.zshrc` is a plain file written by pauldot — not a symlink. Pauldot detects its own output via the `PAULDOT_HEADER` constant on the first line.

`apply` concatenates the profile's source files in order and writes the result:

```zsh
# PAULDOT_HEADER — managed by pauldot. Run `pauldot apply` to regenerate.

# --- zshrc.base ---
<contents of files/zshrc.base>

# --- zshrc.work ---
<contents of files/zshrc.work>

# --- aliases.zsh ---
<contents of files/aliases.zsh>

# --- env ---
export WORK_MODE="true"
export EDITOR="zed --wait"
```

An existing `~/.zshrc` without the `PAULDOT_HEADER` is backed up to `~/.zshrc.bak.<timestamp>` before being replaced. An existing file that already has the header is overwritten in place.

## How dotfile tracking works

`pauldot track <path>` brings an existing dotfile under repo management:

1. Copy `~/<path>` to `files/home/<path>` in the dotfiles repo
2. Add `"<path>"` to the active profile's `dotfiles` list in `profiles/<name>.toml`
3. If `git.auto_commit = true`, commit the change

The live file is **not** replaced or symlinked — it stays a real file at its original location.

**On `apply`:**

- For each path in the active profile's `dotfiles` list, check if `~/<path>` exists
- If missing: copy from `files/home/<path>` → `~/<path>`
- If present and `--overwrite` is passed: back up the existing file to `<path>.bak.<timestamp>`, then overwrite

**On `pauldot sync`:**

- For each tracked dotfile: compare `~/<path>` (live) vs `files/home/<path>` (repo)
- If only the live version changed: copy live → repo, commit, push
- If only the remote changed: eject with a message to run `pauldot apply --overwrite`
- If both changed: eject with a conflict message
- If neither changed: skip

**Files layout:**

```
files/home/
├── .gitconfig                    # maps to ~/.gitconfig
└── .config/
    └── starship.toml             # maps to ~/.config/starship.toml
```

## Project layout (the pauldot tool itself)

```
pauldot/
├── pyproject.toml                # requires-python = ">=3.14"
├── uv.lock
├── README.md
├── pauldot/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── state.py
│   ├── apply.py
│   ├── tools.py
│   ├── profiles.py
│   ├── git.py
│   ├── gh.py                 # gh CLI wrapper + auth detection
│   ├── shell.py
│   ├── zshrc.py
│   ├── scaffold.py           # `init --scaffold`
│   └── help_text.py          # bootstrap / gh / fork content
├── templates/
│   └── scaffold/             # the example dotfiles structure
└── tests/
    ├── test_config.py
    ├── test_profiles.py
    ├── test_apply.py
    ├── test_tools.py
    ├── test_git.py
    ├── test_alias.py
    ├── test_doctor.py
    └── test_scaffold.py
```

All commands assume `uv`. README examples consistently use `uv run pauldot ...` for development and `uv tool install pauldot` for users.

## Staged build plan

### v0.1 — single profile, one file ✓

- [x] `pauldot apply` symlinks `~/.zshrc` to a hardcoded file
- [x] `pauldot status` dry-run

### v0.2 — TOML config, profiles, init ✓

- [x] `pauldot.toml`, `profiles/*.toml`
- [x] `pauldot init <repo-url>` with state.toml
- [x] `pauldot profile show / set / list`
- [x] Generated zshrc sourcing base + profile + aliases

### v0.3 — tools ✓

- [x] `tools/tools.toml`
- [x] `pauldot tool list / install / add / remove`
- [x] OS detection
- [x] Apply runs tool reconciliation

### v0.4 — quality of life ✓

- [x] `pauldot alias add`
- [x] `pauldot edit`
- [x] `pauldot doctor`
- [x] `pauldot sync`
- [x] Auto-commit hooks
- [x] `pauldot help gh` and `pauldot help bootstrap`

### v0.5 — encryption — skipped, out of scope

### v0.6 — fork-friendliness and distribution ✓

- [x] `pauldot init --scaffold`
- [x] `pauldot help fork`
- [x] `bootstrap.sh` template in scaffold
- [x] GitHub Actions for PyPI publishing
- [x] README polish

### v0.7 — absorb ✓

- [x] `pauldot absorb` command
- [x] `absorb.py` module with diff + append logic
- [x] `--dry-run` flag on absorb
- [x] `--target` flag to choose destination file (defaults to `zshrc.base`)
- [x] Auto-commit absorbed changes if `git.auto_commit = true`
- [x] Tests for absorb logic

### Refactor phases ✓

- [x] Refactor 1 — Zshrc engine: plain-file output, drop symlink model, `PAULDOT_HEADER` detection
- [x] Refactor 2 — Profile system: env export inline, auto-apply on alias add + profile set, `display.py`
- [x] Refactor 3 — Tool streaming: always-stream subprocess output, `pauldot tool update`
- [x] Refactor 4 — Dotfile tracking: `pauldot track`, per-profile `dotfiles` list, `files/home/` layout
- [x] Refactor 6 — Documentation: flow docs, mermaid diagrams, README, SPEC.md

### Beyond — defer

- Brewfile/Aptfile generation from `tools.toml`
- Per-machine overrides (currently profiles are by purpose, not by machine)
- Tool dependency ordering (`requires = ["brew"]`)

## Design principles

- **The repo is the source of truth.** Local state is just "which profile, which repo URL".
- **Idempotent apply.** Run it ten times, same result.
- **Fork-friendly by construction.** No hardcoded usernames, repo URLs, or assumptions baked into the code.
- **Fail loud, recover gracefully.** Tool install failures don't abort the apply loop.
- **No magic.** Plain TOML, plain zsh, plain files.
- **`uv` everywhere.** Development, installation, distribution. No `pip`, no virtualenvs by hand.

## Resolved decisions

- **Plain file for `~/.zshrc`** (not a symlink) — pauldot writes it directly and detects its own output via `PAULDOT_HEADER`; symlink model was dropped in Refactor 1
- **`uv` is the bootstrap dep** — installed first, installs everything else
- **`apply` and `sync` are separate** — apply is deterministic from local state
- **`pauldot.toml` is committed** so forks customise it; the dotfiles repo URL itself is local-only
- **Tracked dotfiles are copies, not symlinks** — apps can write to them freely; `sync` reconciles drift
