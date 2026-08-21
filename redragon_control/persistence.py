from __future__ import annotations

import os
from pathlib import Path

from .config import Profile, parse, parse_active_profile, serialize


def state_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    root = Path(config_home) if config_home else Path.home() / ".config"
    return root / "redragon-control" / "state.ini"


def load_state(path: Path | None = None) -> tuple[list[Profile], int]:
    text = (path or state_path()).read_text(encoding="utf-8")
    return parse(text), parse_active_profile(text)


def save_state(profiles: list[Profile], active_profile: int, path: Path | None = None) -> None:
    destination = path or state_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(serialize(profiles, active_profile), encoding="utf-8")
    temporary.replace(destination)
