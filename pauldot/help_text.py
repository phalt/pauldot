"""Content for `pauldot help bootstrap`, `help gh`, and `help fork`."""

GH_HELP = """\
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
     pauldot init git@github.com:<you>/dotfiles\
"""

BOOTSTRAP_HELP = """\
Bootstrapping pauldot on a new machine
───────────────────────────────────────

1. Install uv (if missing):
     curl -LsSf https://astral.sh/uv/install.sh | sh

2. Install pauldot:
     uv tool install pauldot

3. If your dotfiles repo is PRIVATE, set up GitHub CLI first:
     pauldot help gh

4. Clone your dotfiles repo and configure this machine:
     pauldot init git@github.com:<you>/dotfiles

5. Apply:
     pauldot apply

6. Open a new shell or source the generated config:
     source ~/.zshrc\
"""

FORK_HELP = """\
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

6. On other machines, either use the bootstrap script:
     curl -sSL https://raw.githubusercontent.com/<you>/dotfiles/main/bootstrap.sh | sh

   Or, if pauldot is already installed:
     pauldot init git@github.com:<you>/dotfiles
     pauldot apply

That's it. pauldot itself is unchanged — you just point it at your repo.\
"""
