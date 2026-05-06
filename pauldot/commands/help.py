"""Help subcommands: gh, bootstrap, fork."""

import typer
from rich import console as rich_console

from pauldot import help_text

help_app = typer.Typer()

console = rich_console.Console()


@help_app.command("gh")
def help_gh() -> None:
    """GitHub CLI setup walkthrough for private dotfiles repos."""
    console.print(help_text.GH_HELP)


@help_app.command("bootstrap")
def help_bootstrap() -> None:
    """How to bootstrap pauldot on a new machine."""
    console.print(help_text.BOOTSTRAP_HELP)


@help_app.command("fork")
def help_fork() -> None:
    """How to set up your own dotfiles repo with pauldot."""
    console.print(help_text.FORK_HELP)
