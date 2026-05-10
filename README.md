# pauldot

Pauldot is a terminal and tooling configuration manager for users who want to keep their configuration across multiple machines in sync.

Use it to manage:

- Aliases
- Dotfiles
- Tools
- Environment variables
- Profiles


## Install

```sh
uv tool install pauldot
```

## Quick start (new dotfiles repo)

```sh
# 1. Create your dotfiles repo on GitHub
gh repo create <you>/dotfiles --private --clone

# 2. Scaffold the structure
pauldot init --scaffold ./dotfiles

# 3. If you have an existing ~/.zshrc, migrate it in
pauldot migrate

# 4. Edit pauldot.toml and bootstrap.sh, then push
cd dotfiles && git add . && git commit -m "init" && git push

# 5. On any new machine
curl -sSL https://raw.githubusercontent.com/<you>/dotfiles/main/bootstrap.sh | sh
```

Run `pauldot help fork` for the full walkthrough.

## Quick start (existing dotfiles repo, new machine)

```sh
pauldot init git@github.com:<you>/dotfiles

# If this machine already has a ~/.zshrc, bring it under management first
pauldot migrate --dry-run   # preview what will be absorbed
pauldot migrate             # write aliases → aliases.zsh, rest → zshrc.base

pauldot apply
```

If your repo is private, set up GitHub CLI first — `pauldot help gh` walks you through it.

## Commands

```
pauldot init [<repo-url>]        Clone your dotfiles repo and configure this machine
pauldot init --scaffold <path>   Generate a starter dotfiles repo structure
pauldot apply                    Reconcile current profile (zshrc + tools + dotfiles)
pauldot apply --overwrite        Also overwrite existing dotfiles from repo (backs up first)
pauldot status                   Dry-run apply — show what would change
pauldot doctor                   Health check

pauldot migrate                  Migrate an existing ~/.zshrc into your dotfiles repo
pauldot migrate --dry-run        Preview what would be migrated without writing anything

pauldot track <path>             Start tracking a dotfile: copy it into the repo
pauldot sync                     Pull remote changes; push local edits
pauldot clean                    List backup files left by pauldot (dry-run)
pauldot clean --yes              Delete all backup files

pauldot profile show             Show the active profile
pauldot profile list             List available profiles
pauldot profile set <name>       Switch profile

pauldot tool list                List all defined tools and install status
pauldot tool install [<name>]    Install a tool (or all profile tools)
pauldot tool add                 Interactively add a tool to tools.toml
pauldot tool remove <name>       Remove a tool from tools.toml

pauldot alias add <key> <value>  Add an alias to aliases.zsh
pauldot alias list               List defined aliases

pauldot absorb                   Absorb external zshrc modifications into source files
pauldot absorb --dry-run         Show what would be absorbed without writing
pauldot absorb --target <file>   Absorb into a specific source file (default: zshrc.base)
pauldot edit [profile|tools|zshrc|pauldot]  Open a dotfiles file in $EDITOR

pauldot help bootstrap           Bootstrap walkthrough for new machines
pauldot help gh                  GitHub CLI auth walkthrough
pauldot help fork                How to set up your own dotfiles repo
```

## Dotfiles

pauldot tracks dotfiles in `files/home/` inside your repo. A file tracked at `files/home/.gitconfig` maps to `~/.gitconfig` on each machine.

```sh
pauldot track ~/.gitconfig       # copies to files/home/.gitconfig, adds to profile
pauldot apply                    # bootstraps missing dotfiles on a new machine
pauldot apply --overwrite        # pull repo version to live (with backup)
pauldot sync                     # copies live edits into repo and pushes
```

**Backups.** Whenever pauldot replaces an existing file — during `apply` on first run (for `~/.zshrc`) or `apply --overwrite` (for tracked dotfiles) — the original is backed up to `<file>.bak.<timestamp>` in the same directory. Run `pauldot clean` to list them; `pauldot clean --yes` to delete.

**Sync behaviour.** `pauldot sync` detects per-file what changed on each side since the last pull:

| Outcome | What happened | What sync does |
|---|---|---|
| `no_change` | Live matches repo | Nothing |
| `synced` | Only live changed | Copies live → repo, commits, pushes |
| `remote_updated` | Only remote changed | Ejects — run `pauldot apply --overwrite` |
| `conflict` | Both sides changed | Ejects — resolve manually or run `apply --overwrite` |

If sync ejects due to `remote_updated` or `conflict`, it records the unresolved paths in `~/.config/pauldot/sync_state.toml`. Running sync again without resolving will eject again — it will never silently overwrite a remote change with a stale local file.

## Dotfiles repo layout

```
~/.pauldot/
├── pauldot.toml           # top-level config (shell, git, bootstrap settings)
├── profiles/
│   ├── base.toml          # shared base profile
│   └── personal.toml      # extends base; machine-specific overrides
├── files/
│   ├── zshrc.base         # base zsh config
│   ├── zshrc.personal     # profile-specific zsh config
│   ├── aliases.zsh        # managed by `pauldot alias add`
│   └── home/
│       ├── .gitconfig     # tracked dotfiles (copied to ~ on apply)
│       └── .config/
│           └── starship.toml
├── tools/
│   └── tools.toml         # tool definitions (check + install commands)
└── bootstrap.sh           # one-liner for new machines
```

`~/.zshrc` is a plain file written by pauldot (not a symlink). It is regenerated by `apply` each time your profile changes.

## Local state

```
~/.config/pauldot/state.toml   # active profile, repo URL, and any unresolved sync issues (not committed)
```

## Development

```sh
make install    # uv sync
make test       # uv run pytest
make lint       # uv run ruff check .
make format     # uv run ruff format .
```

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).
