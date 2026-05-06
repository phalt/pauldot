"""Pydantic models and loading for pauldot.toml, profiles, and tools."""

import pathlib
import tomllib
import typing

import pydantic
import tomli_w


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


class ToolInstall(pydantic.BaseModel):
    macos: str | None = None
    linux: str | None = None


class ToolDefinition(pydantic.BaseModel):
    name: str
    check: str
    install: ToolInstall = pydantic.Field(default_factory=ToolInstall)


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


def load_tools(repo_path: pathlib.Path) -> list[ToolDefinition]:
    """Load tool definitions from tools/tools.toml. Returns empty list if file doesn't exist."""
    path = repo_path / "tools" / "tools.toml"
    if not path.exists():
        return []
    with path.open("rb") as f:
        data = tomllib.load(f)
    return [ToolDefinition.model_validate(t) for t in data.get("tool", [])]


def save_tools(repo_path: pathlib.Path, tool_list: list[ToolDefinition]) -> None:
    """Write tool definitions back to tools/tools.toml."""
    path = repo_path / "tools" / "tools.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"tool": [t.model_dump(exclude_none=True) for t in tool_list]}
    path.write_bytes(tomli_w.dumps(data).encode())
