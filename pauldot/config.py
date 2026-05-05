"""Pydantic models and loading for pauldot.toml and profile files."""

import pathlib
import tomllib
import typing

import pydantic


class CoreConfig(pydantic.BaseModel):
    default_profile: str = "personal"
    shell: str = "zsh"


class GitConfig(pydantic.BaseModel):
    auto_commit: bool = True
    auto_push: bool = False
    default_branch: str = "main"
    visibility: typing.Literal["private", "public"] = "private"


class EncryptionConfig(pydantic.BaseModel):
    enabled: bool = False
    recipients_file: str = "secrets/recipients.txt"


class BootstrapConfig(pydantic.BaseModel):
    require_gh_auth: bool = True


class PauldotConfig(pydantic.BaseModel):
    core: CoreConfig = pydantic.Field(default_factory=CoreConfig)
    git: GitConfig = pydantic.Field(default_factory=GitConfig)
    encryption: EncryptionConfig = pydantic.Field(default_factory=EncryptionConfig)
    bootstrap: BootstrapConfig = pydantic.Field(default_factory=BootstrapConfig)


class ProfileConfig(pydantic.BaseModel):
    extends: str | None = None
    zshrc: str | None = None
    tools: list[str] = pydantic.Field(default_factory=list)
    secrets: str | None = None
    env: dict[str, str] = pydantic.Field(default_factory=dict)


def load_pauldot_config(repo_path: pathlib.Path) -> PauldotConfig:
    """Load and validate pauldot.toml from the dotfiles repo."""
    path = repo_path / "pauldot.toml"
    if not path.exists():
        raise FileNotFoundError(f"pauldot.toml not found at {path}.\nIs this a valid pauldot dotfiles repo?")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return PauldotConfig.model_validate(data)


def load_profile(repo_path: pathlib.Path, name: str) -> ProfileConfig:
    """Load and validate profiles/<name>.toml from the dotfiles repo."""
    path = repo_path / "profiles" / f"{name}.toml"
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{name}' not found at {path}.\nRun `pauldot profile list` to see available profiles."
        )
    with path.open("rb") as f:
        data = tomllib.load(f)
    return ProfileConfig.model_validate(data)


def list_profiles(repo_path: pathlib.Path) -> list[str]:
    """Return sorted names of all profiles in profiles/."""
    profiles_dir = repo_path / "profiles"
    if not profiles_dir.exists():
        return []
    return sorted(p.stem for p in profiles_dir.glob("*.toml"))
