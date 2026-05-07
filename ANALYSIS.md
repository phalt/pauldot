# Pauldot: Critical Usability Assessment

**Comparative analysis against chezmoi and yadm**
**Author:** Claude Code · **Date:** 2026-05-06

---

## Executive Summary

Pauldot has a clear and distinctive niche — tool reconciliation and alias management as first-class shell-setup concerns — but it has overcomplicated the one thing it must absolutely nail (managing `~/.zshrc`) and left untouched the one thing users of these tools universally need (managing *all* their dotfiles, not just `~/.zshrc`). This document diagnoses those gaps, identifies pauldot's genuine strengths, and recommends concrete improvements.

---

## 1. How the Competitors Work

### 1.1 chezmoi

**Mental model:** Source state → target state. Files live in `~/.local/share/chezmoi` (tracked in a normal git repo), and `chezmoi apply` copies/renders them into your home directory. The key verbs are:

| Verb | What it does |
|---|---|
| `chezmoi add ~/.gitconfig` | Copies a live file into the source repo |
| `chezmoi edit ~/.gitconfig` | Opens the source file; apply writes back |
| `chezmoi diff` | Shows what would change before applying |
| `chezmoi apply` | Reconciles source → home directory |
| `chezmoi re-add ~/.gitconfig` | Pulls live edits back into the source repo |
| `chezmoi status` | Shows which managed files have drifted |

Multi-machine differences are handled with **Go templates** inside source files. A `.gitconfig.tmpl` can conditionally include a work email on the work laptop. Templates can read from password managers (1Password, Bitwarden, etc.) so secrets never touch the repository.

**What it manages:** Any file in `$HOME` — `.gitconfig`, `.vimrc`, `.tmux.conf`, `.ssh/config`, `.bashrc`, `.zshrc`, everything. No concept of "shell" or "tools" — you write a script (stored in `~/.local/share/chezmoi/run_once_install_tools.sh`) that chezmoi runs after apply.

### 1.2 yadm

**Mental model:** A bare git repository (`~/.local/share/yadm/repo.git`) that tracks files directly in your home directory. Files stay where they are — no copy, no apply step. The key verbs are exactly git's verbs prefixed with `yadm`:

| Verb | What it does |
|---|---|
| `yadm add ~/.gitconfig` | Starts tracking a live file |
| `yadm commit -m "..."` | Commits tracked changes |
| `yadm push` | Pushes to remote |
| `yadm clone <url>` | Clones and checks out on a new machine — files immediately in place |
| `yadm alt` | Creates symlinks for OS/hostname-specific alternate files |

Multi-machine differences are handled with **file naming conventions**: `~/.gitconfig##os.Linux` vs `~/.gitconfig##os.Darwin`. yadm automatically symlinks the right variant. Post-clone tool installation is handled by a bootstrap script you write yourself.

**What it manages:** Any file in `$HOME`. No concept of "tools" or "aliases".

---

## 2. Where Pauldot Stands Today

### 2.1 What pauldot actually does

```
pauldot init <url>        Clone dotfiles repo, set active profile
pauldot apply             Generate .zshrc.generated, symlink ~/.zshrc, install missing tools
pauldot status            Dry-run apply
pauldot sync              Git pull/push dotfiles repo
pauldot migrate           Pull existing ~/.zshrc into the repo's source files
pauldot absorb            Pull external modifications to .zshrc.generated back into source files
pauldot edit <target>     Open profile|zshrc|tools|pauldot in $EDITOR
pauldot doctor            Health check
pauldot alias add/list    Manage aliases in files/aliases.zsh
pauldot profile show/list/set   Manage the active profile
pauldot tool add/remove/list/install  Manage tool definitions and installs
pauldot help ...          Bootstrap / gh / fork walkthrough
```

The apply pipeline:
1. Load `state.toml` (active profile)
2. Load `pauldot.toml` (validate repo)
3. Resolve profile + `extends` chain
4. Write `~/.pauldot/files/.zshrc.generated` — a file that `source`s each zshrc file, then `aliases.zsh`, then `.env.generated`
5. Symlink `~/.zshrc` → `.zshrc.generated`
6. Reconcile tools (check + install missing)

### 2.2 The scope of pauldot's dotfile management

| Dotfile | chezmoi | yadm | pauldot |
|---|---|---|---|
| `~/.zshrc` | yes | yes | yes (generated) |
| `~/.gitconfig` | yes | yes | **no** |
| `~/.vimrc` / `~/.config/nvim/` | yes | yes | **no** |
| `~/.tmux.conf` | yes | yes | **no** |
| `~/.ssh/config` | yes (with encryption) | yes (with encryption) | **no** |
| `~/.config/starship.toml` | yes | yes | **no** |
| Any XDG config | yes | yes | **no** |

Pauldot manages exactly one dotfile — `~/.zshrc` — and it manages it in an indirect way. For every other config file a developer carries between machines, they are on their own.

---

## 3. Pauldot's Genuine Advantages

These are real differentiators — features the competitors do not provide and that are worth preserving and building on.

### 3.1 Tool reconciliation as a first-class citizen

Neither chezmoi nor yadm has a built-in concept of "this machine should have these tools installed; check and install them if missing." They both rely on you writing bootstrap scripts or `run_once_` scripts that you must maintain yourself.

Pauldot's `tools/tools.toml` + `pauldot apply` gives you a **declarative tool manifest** with OS-specific install commands, idempotent check-then-install logic, and a summary of what happened. `pauldot tool add` lets you add tools interactively without editing TOML by hand.

This is the strongest card in pauldot's hand.

### 3.2 Alias management as a first-class citizen

`pauldot alias add foo "bar baz"` lets you add an alias from the command line without opening a file. `pauldot alias list` gives you a quick table. This is quality-of-life that chezmoi and yadm simply don't provide — with them, you open the file, add the alias, commit, push, done.

### 3.3 Profile system with explicit inheritance

The `extends` profile system is a clean model for "work laptop" vs "personal laptop" configurations. Neither chezmoi nor yadm offer this as a named concept — chezmoi does it through templates and variables, yadm through file naming conventions. Pauldot's model is easier to explain and reason about.

### 3.4 Explicit `--dry-run` on the core operation

`pauldot status` dry-runs the entire apply pipeline and shows what would change. chezmoi has `chezmoi diff` and `chezmoi status`; yadm does not have a dry-run mode. Pauldot's dry-run is well-implemented.

---

## 4. Pauldot's Gaps and Problems

### 4.1 Critical gap: only manages ~/.zshrc

This is the single biggest problem. If someone is evaluating pauldot against chezmoi or yadm, the first question is "what do you manage?" The answer "just your `.zshrc`" will lose the comparison immediately.

The entire value proposition of a dotfiles manager is that you can set up a fresh machine in minutes. With pauldot, you still have to manually configure `~/.gitconfig`, `~/.vimrc`, `~/.tmux.conf`, your editor settings, starship config, and anything else that lives in `$HOME` or `~/.config/`. That is most of what a developer cares about.

### 4.2 Design problem: the generated file that sources other files

This is the root cause of several downstream problems.

`~/.zshrc` is a symlink to `~/.pauldot/files/.zshrc.generated`. That generated file contains:

```zsh
# Generated by pauldot. Do not edit directly.
source /home/paul/.pauldot/files/zshrc.base
source /home/paul/.pauldot/files/aliases.zsh
[ -f /home/paul/.pauldot/files/.env.generated ] && source /home/paul/.pauldot/files/.env.generated
```

This design creates a chain of problems:

**Problem A: External tools break the model.** Tools like pyenv, nvm, and Homebrew detect `~/.zshrc` and append to it. They append to the *generated* file — not to any source file. This is why `pauldot absorb` exists. The command exists to paper over a fundamental design flaw.

**Problem B: Debugging is harder.** When a user's shell breaks, they look at `~/.zshrc`. They see a generated file they were told not to edit, with paths into a hidden `.pauldot` directory. This is confusing.

**Problem C: The generated file can diverge.** The absorb command's fallback set-diff logic suggests the generated file has already diverged in unexpected ways in practice. This is fragility built into the design.

**Problem D: `pauldot apply` is required after every profile change but not after every edit.** Because `~/.zshrc` just sources the actual files, edits to `zshrc.base` take effect at the next shell start without running `pauldot apply`. But `pauldot apply` *is* required when profile config changes. This is confusing — "do I need to apply or not?"

A simpler design: `~/.zshrc` is a direct symlink to one source file in the repo. No generated intermediary. External tools that append to `~/.zshrc` would append to a file that is under version control — which is exactly where you want those changes to land.

### 4.3 The two-stage init workflow has invisible failure modes

`pauldot init <url>` clones the repo and sets the active profile, but does *not* apply. The user must remember to run `pauldot apply` separately. If they forget, `~/.zshrc` is still their old file.

Compare: `chezmoi init --apply $GITHUB_USERNAME` — one command, new machine fully configured.

### 4.4 sync does not apply after pulling

`pauldot sync` pulls from remote and pushes local commits. If there were changes pulled from remote (e.g., you made changes on another machine), the user must separately run `pauldot apply` to have those changes take effect. The tool doesn't tell them this.

### 4.5 Profiles only govern zshrc + tools, not machine-specific config

The profile system can select different zshrc files and different tool lists, but since pauldot doesn't manage other dotfiles, there's no way to use profiles to, say, swap `.gitconfig` between work and personal. This limits the profile system's usefulness.

### 4.6 No shell completions

Neither chezmoi nor yadm (via git) are as deep as pauldot's subcommand tree. Pauldot has `alias`, `profile`, `tool`, `help` groups each with their own subcommands. Without tab completion, discovering commands is laborious.

### 4.7 absorb and migrate are confusingly similar

`migrate` — takes your existing `~/.zshrc` and splits it into `files/zshrc.base` + `files/aliases.zsh`. Used once, on first setup.

`absorb` — takes the current `~/.zshrc.generated` (which may have been modified by external tools) and appends the extra lines to a source file. Used on an ongoing basis.

Both are "pull reality back into the repo." The conceptual distinction is clear in theory but users will confuse them. They're both asking: "my shell has stuff in it that isn't in my dotfiles repo — how do I fix that?"

### 4.8 `pauldot edit` only works for four specific targets

`pauldot edit profile | tools | zshrc | pauldot` — exactly four hardcoded targets. Any other file pauldot doesn't manage (which is most files) requires the user to know where it lives and open it directly.

---

## 5. Recommended Improvements

These are listed in priority order — addressing the most critical gaps first.

### Priority 1: Manage all dotfiles via symlinks

**The change:** Add a `pauldot track <file>` command (analogous to `chezmoi add` or `yadm add`) that:
1. Copies the file into `~/.pauldot/files/` (preserving its relative path from `$HOME`)
2. Creates a symlink from the original location to the copy in the repo
3. Commits if `auto_commit = true`

Add `pauldot apply` to ensure all tracked symlinks exist (repair missing/broken links).

**Why this matters:** This closes the fundamental gap. A user can now track `.gitconfig`, `.vimrc`, starship config, everything — not just `.zshrc`.

**What this looks like:**

```
pauldot track ~/.gitconfig           # copies to files/dot_gitconfig, symlinks back
pauldot track ~/.config/starship.toml  # copies to files/config/dot_starship.toml
pauldot apply                        # ensures all tracked symlinks are in place
```

The profile system already supports a `files:` key or similar — profiles can specify which tracked files to apply, allowing work vs. personal setups to activate different sets.

### Priority 2: Fix the zshrc model — drop the generated intermediary

**The change:** Instead of generating a file that sources other files, concatenate the profile's zshrc sources into a single `~/.zshrc` (or symlink directly to a single source file if the profile has exactly one). Alternatively: make the single source file *be* `~/.zshrc` by symlinking `~/.zshrc` directly to `files/zshrc.base`.

**Why this matters:** Eliminates the `absorb` command's reason for existence. Eliminates the "do not edit" generated file. Eliminates the fragility of external tools appending to a managed file. Makes shell debugging straightforward.

**Migration path:** `pauldot migrate` already exists to pull a real `~/.zshrc` into source files. Add a `migrate` step that concatenates current source files into a single `files/zshrc` and updates the symlink target.

### Priority 3: Make `init` apply by default (or prompt)

**The change:** After a successful `pauldot init`, ask the user: "Run `pauldot apply` now? [Y/n]" and do it if they say yes. Or add `--apply` flag: `pauldot init --apply <url>`.

**Why this matters:** Brings the new-machine workflow down to a single command. Matches chezmoi's `init --apply` and yadm's implicit apply-on-clone.

### Priority 4: Make `sync` apply after pull

**The change:** After a successful `git pull` that brought in new commits, automatically run `pauldot apply` (or prompt: "Changes pulled. Apply now? [Y/n]").

**Why this matters:** The loop "sync → apply" is always the right sequence. Making the user do it manually adds friction and creates a state where the repo and the machine are out of sync without any warning.

### Priority 5: Add shell completions

**The change:** Use typer's built-in `--install-completion` / `--show-completion` (which it already supports) and document this in `pauldot help bootstrap` and the scaffold's README.

**Why this matters:** With `alias`, `profile`, `tool`, and `help` groups each having subcommands, tab completion is the difference between pauldot feeling polished and feeling like a chore.

### Priority 6: Merge `absorb` into `migrate`; rename with intent

With Priority 2 completed, `absorb` becomes obsolete. With Priority 1 completed, `migrate` has a broader purpose.

The remaining function of `migrate` — importing an existing dotfile into pauldot's tracking — should become `pauldot track --migrate ~/.zshrc` or simply a step in `pauldot track` that handles the case where the file already exists at the destination.

---

## 6. What Pauldot Should *Not* Try to Do

These are things chezmoi does that pauldot should not copy. They are complex and out of scope for what makes pauldot distinctive.

- **Go template system for machine-specific config** — the profile + `extends` system handles this more readably for the use case pauldot targets.
- **Password manager integration** — this is sophisticated infrastructure. A better answer for pauldot is: "encrypt your secrets with age and document the workflow."
- **Windows support** — pauldot's zsh-first design is its constraint and its clarity. Stay on macOS/Linux.
- **Watch mode** — adds complexity for minimal gain. The symlink model means file edits take effect at the next shell start automatically.

---

## 7. The Ideal Pauldot Workflow (Post-Improvement)

This is what pauldot should feel like after the improvements above:

### First time on a new machine
```
# Install pauldot, then:
pauldot init --apply https://github.com/yourname/dotfiles
# → clones repo, sets profile, applies (symlinks all tracked dotfiles), installs tools
```

### Day-to-day editing
```
pauldot edit zshrc        # opens ~/.pauldot/files/zshrc.base in $EDITOR
# (change takes effect on next shell start — it's a symlink source)

pauldot alias add gs "git status"   # add alias, auto-commit
```

### Tracking a new dotfile
```
pauldot track ~/.gitconfig   # copies to repo, creates symlink, auto-commit
```

### Getting updates from another machine
```
pauldot sync    # pull → apply → push
```

### Health check
```
pauldot doctor  # shows any broken symlinks, missing tools, state issues
pauldot status  # dry-run: shows what apply would do
```

---

## 8. Summary Table

| Dimension | chezmoi | yadm | pauldot (now) | pauldot (ideal) |
|---|---|---|---|---|
| Manages all dotfiles | yes | yes | **no** | yes |
| Tool reconciliation | no (scripts) | no (scripts) | **yes** | yes |
| Alias management | no | no | **yes** | yes |
| Profile system | template vars | file naming | **extends chain** | extends chain |
| New machine: one command | yes | yes | **no (2 steps)** | yes |
| Drift detection | explicit | git-based | dry-run | dry-run + tracked symlinks |
| Secrets | password managers | GPG archive | **none** | planned (age) |
| Shell completions | yes | via git | **no** | yes |
| Learning curve | medium | low (git) | low | low |
| Conceptual simplicity | medium | high | medium | high |
| Zsh-specific features | no | no | **yes (absorb, aliases)** | yes |

---

## 9. Notes for the Coding Tool

The following concrete file-level changes correspond to the priority improvements above.

**Priority 1 (track command):**
- Add `pauldot/track.py` — implements file-to-repo copy + symlink creation. Files stored under `files/home/` preserving path structure.
- Add `TrackedFile` model to `config.py` — `path: str` (relative from `$HOME`), optional per-profile
- Extend `pauldot.toml` schema in `config.py`: `[tracked] files = [...]` or equivalent
- Add `track` command to `cli.py`
- Extend `apply.py` to reconcile tracked symlinks (ensure each tracked file's symlink exists and points to the repo copy)
- Extend `doctor` in `cli.py` to check tracked symlink health

**Priority 2 (drop generated intermediary):**
- Rewrite `zshrc.py`: `generate_zshrc` concatenates source files rather than writing `source` lines. Or simplify to single-source-file model where `~/.zshrc` symlinks directly to `files/zshrc.base`.
- Remove `absorb.py` once the generated file model is gone (the absorb problem disappears)
- Update `migrate.py` to write a single `files/zshrc` rather than split into base + aliases (aliases.zsh still separate, but the base zshrc is now the single truth)
- Update tests in `test_apply.py`, `test_absorb.py`

**Priority 3 (init --apply):**
- Add `--apply` flag to `init` command in `cli.py`
- After successful `state.save_state(...)`, if `--apply`, call `pauldot_apply.run(home)`

**Priority 4 (sync → apply):**
- In `sync` command in `cli.py`, after `git.pull_rebase(repo_path)`, check if any commits were pulled (`git.has_new_commits` — new helper in `git.py`). If yes, call `pauldot_apply.run(home)` or prompt.

**Priority 5 (completions):**
- Add to `pauldot help bootstrap` text: instruction to run `pauldot --install-completion` after install
- Add to scaffold's `bootstrap.sh`

**Priority 6 (merge absorb/migrate):**
- After Priority 2, `absorb.py` can be deleted. `migrate.py` role narrows to one-time import of a pre-existing `~/.zshrc`.
- Consider renaming `migrate` to `import` for clarity: `pauldot import ~/.zshrc`
