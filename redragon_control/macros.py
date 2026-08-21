from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Macro:
    name: str
    actions: list[str] = field(default_factory=list)


def default_macros() -> list[Macro]:
    return [Macro(name=f"Macro {index}") for index in range(1, 16)]


def macros_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "redragon-control" / "macros.json"


def load_macros(path: Path | None = None) -> list[Macro]:
    payload = json.loads((path or macros_path()).read_text(encoding="utf-8"))
    result = [Macro(**item) for item in payload.get("macros", [])]
    return (result + default_macros())[:15]


def save_macros(macros: list[Macro], path: Path | None = None) -> None:
    destination = path or macros_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"version": 1, "macros": [{"name": item.name, "actions": item.actions} for item in macros]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)


def serialize_macros(macros: list[Macro]) -> str:
    lines: list[str] = []
    for index, macro in enumerate(macros[:15], 1):
        if not macro.actions:
            continue
        lines.extend(["", f";## macro{index}"])
        for action in macro.actions:
            clean = action.strip()
            if clean:
                lines.append(f";# {clean}")
    return "\n".join(lines)
