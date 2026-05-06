# pauldot — Specification

A personal system manager: dotfiles, profiles, and tool installations across machines. File-first, written in Python, fork-friendly.

## Goals

- Manage `.zshrc` (and other dotfiles) across multiple machines from a single git repo
- Layer machine-specific profiles (work, personal) on top of a shared base
- Declare desired tools and their install commands; reconcile on apply
- Quick CLI affordances for the daily case (adding aliases, switching profiles)
- One-line bootstrap on a fresh machine
- Support both private and public dotfiles repos via age-encrypted secrets
- Be forkable: the tool ships with no embedded assumptions about whose dotfiles repo it points at

## Non-goals

- Not a general-purpose config manager (no Ansible/Nix ambitions)
- Not cross-shell — zsh only
- No GUI, no daemon, no background sync

## Tech stack

- **Python 3.14**, packaged with `uv`. All project commands use `uv` (`uv run`, `uv sync`, `uv tool install`, `uv build`, etc.) — no bare `python` or `pip`.
- **`typer`** for the CLI
- **`tomllib`** (stdlib) for reading TOML, **`tomli-w`** for writing
- **`pydantic`** for config schema validation
- **`rich`** for output
- **`platformdirs`** for cross-platform paths
- **`age`** (the binary) for encryption — shelled out, not via a Python wrapper
- Shell out to `git` and `gh` via `subprocess`

Everything else is stdlib. No async. No database.

## Two repos, distinct concerns

This matters for the fork story:

1. **`pauldot`** (this codebase) — the CLI tool. Forkable, but most users won't need to.
2. **`<your>-dotfiles`** (the user's repo) — their actual config. Private or public; encrypted secrets where needed.

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
│   └── aliases.zsh
├── tools/
│   └── tools.toml
├── secrets/                      # age-encrypted, safe in public repos
│   ├── recipients.txt
│   ├── work.env.age
│   └── personal.env.age
└── bootstrap.sh
```

## Local state (not in git)

```
~/.config/pauldot/
├── state.toml                    # active profile, dotfiles repo URL, last apply
└── identity.txt                  # this machine's age private key
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

[encryption]
enabled = true
recipients_file = "secrets/recipients.txt"

[bootstrap]
require_gh_auth = true            # private repo → must auth via gh first
```

`visibility` and `encryption.enabled` drive what `pauldot doctor` and `pauldot help bootstrap` say, and what the bootstrap script checks before cloning.

### `profiles/<name>.toml`

```toml
extends = "base"

zshrc = "files/zshrc.work"

tools = ["starship", "zed", "uv", "obsidian", "ripgrep"]

secrets = "secrets/work.env.age"  # optional; decrypted at apply time

[env]
WORK_MODE = "true"
EDITOR = "zed --wait"
```

Single-level extends only — `work` extends `base`, no chains.

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

## Encryption model

Secrets use **age** with the recipients pattern:

- `~/.config/pauldot/identity.txt` is your **private key** — never committed, lives on each machine
- `secrets/recipients.txt` lists **public keys** — committed, one per machine you own
- Files in `secrets/*.age` are encrypted to all recipients; any of your machines can decrypt

Adding a new machine:

1. `pauldot keys generate` — creates a new identity, prints the public key
2. Add the public key to `secrets/recipients.txt` on a machine you already trust
3. `pauldot keys reencrypt` — re-encrypts every `secrets/*.age` to the updated recipient list
4. Commit and push
5. New machine pulls and can now decrypt

At apply time:

- The active profile's `secrets` file is decrypted to `~/.pauldot/files/.env.generated`
- The generated zshrc sources that env file
- The decrypted file is gitignored and never persisted to the repo

If `encryption.enabled = false`, env vars come straight from the profile's `[env]` table and there's no decryption step.

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

pauldot keys generate
pauldot keys show
pauldot keys reencrypt
pauldot secret add <name>
pauldot secret edit <profile>

pauldot sync                         # git pull --rebase, then push if local commits

pauldot help bootstrap               # bootstrap walkthrough
pauldot help fork                    # how to fork & customise
pauldot help gh                      # gh auth walkthrough

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

This machine has no age identity. Generate one now? [Y/n]: y
✓ Generated ~/.config/pauldot/identity.txt
✓ Public key: age1abc...

⚠ Add this public key to secrets/recipients.txt on a machine that can already
  decrypt secrets, then run `pauldot keys reencrypt` there. Until then, this
  machine cannot decrypt existing secrets.

Run `pauldot apply` when ready.
```

`pauldot init` is the only command that writes the dotfiles repo URL into `state.toml`. There's no flag to set it elsewhere — keeps the bootstrap path explicit.

## How `apply` works

1. Load `state.toml`; resolve active profile
2. Load `pauldot.toml` from the repo
3. Resolve profile + extends chain
4. Detect OS (`platform.system()` → `macos` or `linux`)
5. **Encryption setup** (if `encryption.enabled`):
   - Verify identity file exists; fail clearly if not
   - Decrypt the profile's `secrets` file to `~/.pauldot/files/.env.generated`
6. **zshrc reconciliation:**
   - Generate `~/.pauldot/files/.zshrc.generated` (sources base, profile, aliases, env)
   - Back up any existing non-symlink `~/.zshrc` to `~/.zshrc.bak.<timestamp>`
   - Symlink `~/.zshrc` → `~/.pauldot/files/.zshrc.generated`
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
  read REPO_URL
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
     pauldot.toml, profiles/, files/, tools/, secrets/, bootstrap.sh

3. Edit pauldot.toml — set core.default_profile, git.visibility, etc.

4. Edit bootstrap.sh — change the PAULDOT_REPO default to your repo URL.

5. Commit and push:
     cd dotfiles && git add . && git commit -m "init" && git push

6. On other machines:
     curl -sSL https://raw.githubusercontent.com/<you>/dotfiles/main/bootstrap.sh | sh

That's it. pauldot itself is unchanged — you just point it at your repo.
```

## How the generated zshrc works

`~/.zshrc` is a symlink to `~/.pauldot/files/.zshrc.generated`:

```zsh
# Generated by pauldot. Do not edit directly.
# Edit files/zshrc.base, files/zshrc.<profile>, or run `pauldot alias add`.

source ~/.pauldot/files/zshrc.base
source ~/.pauldot/files/zshrc.work
source ~/.pauldot/files/aliases.zsh
[ -f ~/.pauldot/files/.env.generated ] && source ~/.pauldot/files/.env.generated
```

## Project layout (the pauldot tool itself)

```
pauldot/
├── pyproject.toml                # requires-python = ">=3.14"
├── uv.lock
├── README.md
├── src/
│   └── pauldot/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── state.py
│       ├── apply.py
│       ├── tools.py
│       ├── profiles.py
│       ├── git.py
│       ├── gh.py                 # gh CLI wrapper + auth detection
│       ├── shell.py
│       ├── zshrc.py
│       ├── encryption.py         # age wrapper, key management
│       ├── scaffold.py           # `init --scaffold`
│       └── help_text.py          # bootstrap / gh / fork content
├── templates/
│   └── scaffold/                 # the example dotfiles structure
└── tests/
    ├── test_config.py
    ├── test_profiles.py
    ├── test_apply.py
    ├── test_encryption.py
    └── test_scaffold.py
```

All commands assume `uv`. README examples consistently use `uv run pauldot ...` for development and `uv tool install pauldot` for users.

## Staged build plan

### v0.1 — single profile, one file

- [x] `pauldot apply` symlinks `~/.zshrc` to a hardcoded file
- [x] `pauldot status` dry-run
- [x] ~150 lines, proves symlink + backup logic

### v0.2 — TOML config, profiles, init

- [x] `pauldot.toml`, `profiles/*.toml`
- [x] `pauldot init <repo-url>` with state.toml
- [x] `pauldot profile show / set / list`
- [x] Generated zshrc sourcing base + profile + aliases

### v0.3 — tools

- [x] `tools/tools.toml`
- [x] `pauldot tool list / install / add / remove`
- [x] OS detection
- [x] Apply runs tool reconciliation

### v0.4 — quality of life

- `pauldot alias add`
- `pauldot edit`
- `pauldot doctor`
- `pauldot sync`
- Auto-commit hooks
- `pauldot help gh` and `pauldot help bootstrap`

### v0.5 — encryption

- age dependency check
- `pauldot keys generate / show / reencrypt`
- `pauldot secret add / edit`
- Encrypted env loading in apply
- `pauldot.toml` `[encryption]` block honoured

### v0.6 — fork-friendliness and distribution

- `pauldot init --scaffold`
- `pauldot help fork`
- `bootstrap.sh` template in scaffold
- GitHub Actions for PyPI publishing
- README polish

### Beyond — defer

- Brewfile/Aptfile generation from `tools.toml`
- Per-machine overrides (currently profiles are by purpose, not by machine)
- Tool dependency ordering (`requires = ["brew"]`)

## Design principles

- **The repo is the source of truth.** Local state is just "which profile, which repo URL".
- **Idempotent apply.** Run it ten times, same result.
- **Fork-friendly by construction.** No hardcoded usernames, repo URLs, or assumptions baked into the code.
- **Fail loud, recover gracefully.** Tool install failures don't abort the apply loop.
- **No magic.** Plain TOML, plain zsh, plain symlinks. Encrypted files are the one exception, and the encryption tool is industry-standard age.
- **`uv` everywhere.** Development, installation, distribution. No `pip`, no virtualenvs by hand.

## Resolved decisions

- **Symlink for `~/.zshrc`** (not source) — cleaner, easier to detect drift
- **`uv` is the bootstrap dep** — installed first, installs everything else
- **Both private and public repos supported** — encryption is the bridge
- **`apply` and `sync` are separate** — apply is deterministic from local state
- **`pauldot.toml` is committed** so forks customise it; the dotfiles repo URL itself is local-only