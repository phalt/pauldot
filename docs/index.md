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

It manages my dotfiles, my zshrc aliases, and tool installations across my machines. 

It is designed to be File-first, written in Python, and fork-friendly (so you can adapt it to your needs if you want).

## What it does

- Manages `~/.zshrc` aliases and configuration.
- Manages the tools I want installed on my machines.
- Managers machine-specific profiles (`work`, `personal`).
- A quick CLI for daily tasks: adding aliases, switching profiles etc.
- Keeps it all in sync using conflict resolution and state tracking.
- Stores all my configuration in plain text on a git repo.
- Includes a one-line bootstrap for fresh machines.
- Just generates `~/.zshrc` output from your dotfiles repo - never anything complicated or special.

## Install

```sh
uv tool install pauldot
```

## Key concepts

**Your dotfiles are all in one place:**

Pauldot is just a CLI tool that reads your dotfiles repo and generates `~/.zshrc` output.

Your dotfiles are stored in a git repo and are synced to remote origin when you run `pauldot sync`.

The CLI tool is configurable via `~/.config/pauldot/state.toml` so if you change repo URL or branch, `pauldot sync` will use the new configuration.

**The `apply` is always idempotent.** 

Run it as many times as you like and it won't re-run steps that have already been completed.

**The `apply` and `sync` commands are separate.** 

You can run `apply` to apply changes from local state, and `sync` to pull/push changes to remote origin.

**The generated `~/.zshrc` is just like any other shell config file.**

There is no symlink or other magic involved: the generated `~/.zshrc` is just a regular shell script that gets sourced by your shell. It is compiled by Pauldot from the contents in your dotfiles repo.

## Flows

| I want to… | Go to |
|---|---|
| Set up pauldot for the first time | [Bootstrap a new machine](flows/bootstrap.md) |
| Add pauldot to a machine that already has dotfiles | [Migrate an existing machine](flows/migrate.md) |
| Add an alias and get it onto all my machines | [Alias lifecycle](flows/aliases.md) |
| Declare a new tool and install it everywhere | [Tool lifecycle](flows/tools.md) |
| Create a work profile or switch profiles | [Profile lifecycle](flows/profiles.md) |
| Track a dotfile like `.gitconfig` across machines | [Track a dotfile](flows/track.md) |

## Commands

```
pauldot init [<repo-url>]        Clone your dotfiles repo and configure this machine
pauldot init --scaffold <path>   Generate a starter dotfiles repo structure
pauldot apply                    Reconcile current profile (zshrc + dotfiles + tools)
pauldot apply --overwrite        Also overwrite existing dotfiles from repo (backs up first)
pauldot status                   Dry-run apply — show what would change
pauldot doctor                   Health check

pauldot migrate                  Migrate an existing ~/.zshrc into your dotfiles repo
pauldot migrate --dry-run        Preview what would be migrated without writing anything

pauldot track <path>             Start tracking a dotfile: copy it into the repo

pauldot profile show             Show the active profile
pauldot profile list             List available profiles
pauldot profile set <name>       Switch profile
pauldot profile set <name> --apply  Switch profile and apply immediately

pauldot tool list                List all defined tools and install status
pauldot tool install [<name>]    Install a tool (or all profile tools)
pauldot tool add                 Interactively add a tool to tools.toml
pauldot tool remove <name>       Remove a tool from tools.toml

pauldot alias add <key> <value>  Add an alias to aliases.zsh
pauldot alias list               List defined aliases

pauldot sync                     Pull latest changes; push local commits
pauldot clean                    List backup files left by pauldot (dry-run)
pauldot clean --yes              Delete all backup files
pauldot absorb                   Absorb external zshrc modifications into source files
pauldot absorb --dry-run         Show what would be absorbed without writing
pauldot absorb --target <file>   Absorb into a specific source file (default: zshrc.base)
pauldot edit [profile|tools|zshrc|pauldot]  Open a dotfiles file in $EDITOR

pauldot help bootstrap           Bootstrap walkthrough for new machines
pauldot help gh                  GitHub CLI auth walkthrough
pauldot help fork                How to set up your own dotfiles repo
```
