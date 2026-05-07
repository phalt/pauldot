# pauldot
```
                   _     _       _
 _ __   __ _ _   _| | __| | ___ | |_
| '_ \ / _` | | | | |/ _` |/ _ \| __|
| |_) | (_| | |_| | | (_| | (_) | |_
| .__/ \__,_|\__,_|_|\__,_|\___/ \__|
|_|
```

Pauldot is my personal system manager. 

It managers my dotfiles, my zshrc aliases, and tool installations across my machines. 

It is designed to be File-first, written in Python, and fork-friendly (so you can adapt it to your needs if you want).

## What it does

- Manages `~/.zshrc` aliases and configuration.
- Managers the tools I want installed on my machines.
- Layers machine-specific profiles (`work`, `personal`) on top of a shared base.
- Quick CLI for daily tasks: adding aliases, switching profiles etc.
- Keeps it all in sync.
- Stores all my configuration in plain text on a git repo.
- Includes a one-line bootstrap for fresh machines.

## Install

```sh
uv tool install pauldot
```

## Key concepts

**Two respositories:**

- `pauldot` — the CLI tool. Install it once per machine.
- `<you>/dotfiles` — the actual configuration.

The CLI never hardcodes your dotfiles repo URL. It lives in local state (`~/.config/pauldot/state.toml`), set during `pauldot init`.

**`apply` is idempotent.** Run it as many times as you like — it produces the same result every time. It never touches your machine beyond what your dotfiles repo describes.

**`apply` and `sync` are separate.** `apply` reconciles from local state. `sync` handles git pull/push. You control when changes move between machines.

## Flows

| I want to… | Go to |
|---|---|
| Set up pauldot for the first time | [Bootstrap a new machine](flows/bootstrap.md) |
| Add pauldot to a machine that already has dotfiles | [Migrate an existing machine](flows/migrate.md) |
| Add an alias and get it onto all my machines | [Alias lifecycle](flows/aliases.md) |
| Declare a new tool and install it everywhere | [Tool lifecycle](flows/tools.md) |

## Commands

```
pauldot init [<repo-url>]        Clone your dotfiles repo and configure this machine
pauldot init --scaffold <path>   Generate a starter dotfiles repo structure
pauldot apply                    Reconcile current profile (zshrc + tools)
pauldot status                   Dry-run apply — show what would change
pauldot doctor                   Health check

pauldot migrate                  Migrate an existing ~/.zshrc into your dotfiles repo
pauldot migrate --dry-run        Preview what would be migrated without writing anything

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
