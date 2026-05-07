# Bootstrap a new machine

This flow covers setting up pauldot **for the first time** — creating your dotfiles repo from scratch and getting your first machine under management.

If you already have a dotfiles repo and are adding a machine that has existing config, see [Migrate an existing machine](migrate.md) instead.

---

## Overview

```mermaid
flowchart TD
    A([Fresh machine]) --> B[Install uv]
    B --> C["uv tool install pauldot"]
    C --> D{Private dotfiles repo?}

    D -->|Yes| E["pauldot help gh"]
    E --> F["gh auth login"]
    F --> G

    D -->|No / not yet| G["gh repo create you/dotfiles --private --clone"]

    G --> H["pauldot init --scaffold ./dotfiles"]
    H --> I[Edit pauldot.toml\nSet default_profile, visibility, etc.]
    I --> J[Edit bootstrap.sh\nSet PAULDOT_REPO to your repo URL]
    J --> K{Existing ~/.zshrc\nto bring in?}

    K -->|Yes| L["pauldot migrate --dry-run"]
    L --> M{Looks right?}
    M -->|Adjust source files| L
    M -->|Yes| N["pauldot migrate"]
    N --> O

    K -->|No| O["git add . && git commit -m 'init' && git push"]
    O --> P["pauldot init git@github.com:you/dotfiles"]
    P --> Q["pauldot apply"]
    Q --> R(["✓ Machine configured"])
```

---

## Step by step

### 1. Install uv

pauldot is distributed via [uv](https://github.com/astral-sh/uv). Install it first:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install pauldot

```sh
uv tool install pauldot
```

### 3. Authenticate with GitHub (private repos)

If your dotfiles repo will be private, set up GitHub CLI before proceeding:

```sh
pauldot help gh   # walks you through gh auth login
```

### 4. Create and scaffold your dotfiles repo

```sh
gh repo create you/dotfiles --private --clone
pauldot init --scaffold ./dotfiles
```

This writes the skeleton: `pauldot.toml`, `profiles/`, `files/`, `tools/`, and `bootstrap.sh`.

### 5. Configure

Edit `pauldot.toml` — set your `default_profile`, `git.visibility`, and anything else you want.

Edit `bootstrap.sh` — set `PAULDOT_REPO` to your repo's SSH URL.

### 6. Migrate your existing zshrc (optional)

If this machine already has a `~/.zshrc` you want to preserve:

```sh
pauldot migrate --dry-run   # preview: aliases → aliases.zsh, rest → zshrc.base
pauldot migrate             # write it
```

Review the diff before committing.

### 7. Commit and push

```sh
cd dotfiles && git add . && git commit -m "init" && git push
```

### 8. Apply

```sh
pauldot init git@github.com:you/dotfiles
pauldot apply
```

`apply` generates `~/.zshrc`, symlinks it, and installs any declared tools.

Open a new shell — you're done.

---

## On every subsequent machine

```sh
curl -sSL https://raw.githubusercontent.com/you/dotfiles/main/bootstrap.sh | sh
```

Or manually:

```sh
uv tool install pauldot
pauldot init git@github.com:you/dotfiles
pauldot apply
```
