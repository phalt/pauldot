"""The reconciliation engine: load state → resolve profile → generate zshrc → symlink."""

import pathlib

from pauldot import config, profiles, state, zshrc


def run(home: pathlib.Path, dry_run: bool = False) -> zshrc.ZshrcResult:
    """Run the apply pipeline.

    Loads state and config, resolves the active profile, generates .zshrc.generated,
    and symlinks ~/.zshrc to it. Returns the zshrc reconciliation result.
    """
    current_state = state.load_state()
    repo_path = home / ".pauldot"

    config.load_pauldot_config(repo_path)  # validates the repo is a valid pauldot repo
    profile = profiles.resolve(repo_path, current_state.active_profile)

    # generate_zshrc is always called — it's idempotent and non-destructive.
    # dry_run only affects the symlink/backup step in apply_zshrc.
    target = zshrc.generate_zshrc(repo_path, profile)

    return zshrc.apply_zshrc(home, target, dry_run=dry_run)
