# pauldot

Personal system manager: dotfiles, profiles, and tool installations across machines. File-first, written in Python, fork-friendly.

## What it does

- Manages `~/.zshrc` (and other dotfiles) from a single git repo
- Layers machine-specific profiles (work, personal) on top of a shared base
- Declares desired tools and installs them on `apply`
- Quick CLI for daily tasks: adding aliases, switching profiles, syncing
- One-line bootstrap on a fresh machine

## Install

```sh
uv tool install pauldot
```

## Quick start (new dotfiles repo)

```sh
# 1. Create your dotfiles repo on GitHub
gh repo create <you>/dotfiles --private --clone

# 2. Scaffold the structure (optionally porting your existing ~/.zshrc)
pauldot init --scaffold ./dotfiles --port-existing-zshrc

# 3. Edit pauldot.toml and bootstrap.sh, then push
cd dotfiles && git add . && git commit -m "init" && git push

# 4. On any new machine
curl -sSL https://raw.githubusercontent.com/<you>/dotfiles/main/bootstrap.sh | sh
```

`--port-existing-zshrc` is optional but recommended on first setup — it reads your current `~/.zshrc`, moves `alias` lines into `files/aliases.zsh`, and writes everything else into `files/zshrc.base`.

Run `pauldot help fork` for the full walkthrough.

## Quick start (existing dotfiles repo)

```sh
pauldot init git@github.com:<you>/dotfiles
pauldot apply
```

If your repo is private, set up GitHub CLI first — `pauldot help gh` walks you through it.

## Commands

```
pauldot init [<repo-url>]                            Clone your dotfiles repo and configure this machine
pauldot init --scaffold <path>                       Generate a starter dotfiles repo structure
pauldot init --scaffold <path> --port-existing-zshrc  Also port aliases and config from ~/.zshrc into the scaffold
pauldot apply                    Reconcile current profile (zshrc + tools)
pauldot status                   Dry-run apply — show what would change
pauldot doctor                   Health check

pauldot profile show             Show the active profile
pauldot profile list             List available profiles
pauldot profile set <name>       Switch profile

pauldot tool list                List all defined tools and install status
pauldot tool install [<name>]    Install a tool (or all profile tools)
pauldot tool add                 Interactively add a tool to tools.toml
pauldot tool remove <name>       Remove a tool from tools.toml

pauldot alias add <key> <value>  Add an alias to aliases.zsh
pauldot alias list               List defined aliases

pauldot sync                     Pull latest changes; push local commits
pauldot absorb                   Absorb external zshrc modifications into source files
pauldot absorb --dry-run         Show what would be absorbed without writing
pauldot absorb --target <file>   Absorb into a specific source file (default: zshrc.base)
pauldot edit [profile|tools|zshrc|pauldot]  Open a dotfiles file in $EDITOR

pauldot help bootstrap           Bootstrap walkthrough for new machines
pauldot help gh                  GitHub CLI auth walkthrough
pauldot help fork                How to set up your own dotfiles repo
```

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
│   └── aliases.zsh        # managed by `pauldot alias add`
├── tools/
│   └── tools.toml         # tool definitions (check + install commands)
└── bootstrap.sh           # one-liner for new machines
```

`~/.zshrc` is a symlink to a generated file that sources these in order.

## Local state

```
~/.config/pauldot/state.toml    # active profile + repo URL (not committed)
```

## Development

```sh
make install    # uv sync
make test       # uv run pytest
make lint       # uv run ruff check .
make format     # uv run ruff format .
```

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).
