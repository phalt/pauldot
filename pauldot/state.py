"""Read/write ~/.config/pauldot/state.toml."""

import datetime
import pathlib
import tomllib
import typing

import pydantic
import tomli_w


class State(pydantic.BaseModel):
    active_profile: str
    repo_url: str
    last_apply: datetime.datetime | None = None
    # Sync state: paths with unresolved attention from a previous pauldot sync.
    remote_updated: list[str] = []
    conflict: list[str] = []

    @property
    def has_attention(self) -> bool:
        return bool(self.remote_updated or self.conflict)

    def all_pending(self) -> list[tuple[str, typing.Literal["remote_updated", "conflict"]]]:
        return [(p, "remote_updated") for p in self.remote_updated] + [(p, "conflict") for p in self.conflict]


def state_path() -> pathlib.Path:
    return pathlib.Path.home() / ".config" / "pauldot" / "state.toml"


def load_state() -> State:
    """Load state.toml. Raises FileNotFoundError if not initialised."""
    path = state_path()
    if not path.exists():
        raise FileNotFoundError(
            "pauldot has not been initialised on this machine.\nRun `pauldot init <repo-url>` to get started."
        )
    with path.open("rb") as f:
        data = tomllib.load(f)
    return State.model_validate(data)


def save_state(s: State) -> None:
    """Write state.toml, creating the config directory if needed."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = s.model_dump(exclude_none=True)
    path.write_bytes(tomli_w.dumps(data).encode())
