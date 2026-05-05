"""Typer app, command definitions, and subcommand groups."""

import typer

app = typer.Typer()
profile_app = typer.Typer()
tool_app = typer.Typer()
keys_app = typer.Typer()
secret_app = typer.Typer()
help_app = typer.Typer()

app.add_typer(profile_app, name="profile")
app.add_typer(tool_app, name="tool")
app.add_typer(keys_app, name="keys")
app.add_typer(secret_app, name="secret")
app.add_typer(help_app, name="help")
