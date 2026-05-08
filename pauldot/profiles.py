"""Profile resolution and extends chain."""

import pathlib

import pydantic

from pauldot import config


class ResolvedProfile(pydantic.BaseModel):
    name: str
    zshrc_files: list[pathlib.Path]  # in source order: parent first, then child
    tools: list[str]
    env: dict[str, str]
    dotfiles: list[str]  # paths relative to $HOME, parent-first


def resolve(repo_path: pathlib.Path, name: str) -> ResolvedProfile:
    """Resolve a profile, merging its extends parent if present.

    Single-level extends only — see spec.md § Profiles.
    Child values win over parent values on conflict.
    """
    profile = config.load_profile(repo_path, name)

    zshrc_files: list[pathlib.Path] = []
    tools: list[str] = []
    env: dict[str, str] = {}
    dotfiles: list[str] = []

    if profile.extends:
        parent = config.load_profile(repo_path, profile.extends)
        if parent.zshrc:
            zshrc_files.append(repo_path / parent.zshrc)
        tools.extend(parent.tools)
        env.update(parent.env)
        dotfiles.extend(parent.dotfiles)

    if profile.zshrc:
        zshrc_files.append(repo_path / profile.zshrc)
    tools.extend(profile.tools)
    env.update(profile.env)  # child wins on conflicts
    dotfiles.extend(profile.dotfiles)

    return ResolvedProfile(
        name=name,
        zshrc_files=zshrc_files,
        tools=tools,
        env=env,
        dotfiles=dotfiles,
    )
