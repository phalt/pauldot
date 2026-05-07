# Alias lifecycle

This flow covers adding a new alias on one machine, applying it, syncing it to the remote, and picking it up on a second machine.

---

## Overview

```mermaid
sequenceDiagram
    actor U as You (Machine A)
    participant P as pauldot
    participant R as Dotfiles repo (GitHub)
    actor M as Machine B

    U->>P: pauldot alias add ll "ls -la"
    P->>R: Appends alias to files/aliases.zsh
    P->>R: git commit (if auto_commit = true)

    U->>P: pauldot apply
    P->>P: Regenerates .zshrc.generated
    P->>U: ~/.zshrc symlink updated

    Note over U: Open a new shell — ll works ✓

    U->>P: pauldot sync
    P->>R: git push

    Note over M: Later, on Machine B

    M->>P: pauldot sync
    P->>R: git pull
    P->>M: files/aliases.zsh updated locally

    M->>P: pauldot apply
    P->>M: ~/.zshrc symlink updated

    Note over M: Open a new shell — ll works ✓
```

---

## Step by step

### 1. Add the alias

```sh
pauldot alias add ll "ls -la"
```

This appends `alias ll="ls -la"` to `files/aliases.zsh` in your dotfiles repo. If `git.auto_commit = true`, the change is committed immediately.

### 2. Apply it locally

```sh
pauldot apply
```

`apply` regenerates the `~/.zshrc` symlink target to include the updated `aliases.zsh`. Open a new shell (or `source ~/.zshrc`) to use the alias.

### 3. Push to the remote

```sh
pauldot sync
```

`sync` runs `git pull --rebase` then pushes any local commits. After this, the alias is in the remote repo.

### 4. Pull it on another machine

On Machine B:

```sh
pauldot sync    # pulls the latest dotfiles
pauldot apply   # regenerates ~/.zshrc
```

Open a new shell — the alias is available.

---

## Notes

- `pauldot alias list` shows all aliases currently defined in your dotfiles.
- If you want to remove an alias, edit `files/aliases.zsh` directly (`pauldot edit zshrc` opens it in `$EDITOR`), then `apply` and `sync`.
- Aliases live in `files/aliases.zsh` which is sourced by every generated `~/.zshrc`, regardless of profile.
