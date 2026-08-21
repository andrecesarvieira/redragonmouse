from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


VID = "320f"
PID = "5000"

KEYBOARD_MODES = (
    "static",
    "color_wave",
    "color_wave_short",
    "color_wheel",
    "spectrum_cycle",
    "breathing",
    "hurricane",
    "accumulate",
    "starlight",
    "visor",
    "rainbow_circle",
    "vertical_rainbow",
    "blooming",
    "reactive",
    "reactive_ripple",
    "reactive_line",
    "custom",
    "off",
)

OPENRGB_MODES = {
    "static": "Static",
    "color_wave": "Color Wave",
    "color_wave_short": "Color Wave Short",
    "color_wheel": "Color Wheel",
    "spectrum_cycle": "Spectrum Cycle",
    "breathing": "Breathing",
    "hurricane": "Hurricane",
    "accumulate": "Accumulate",
    "starlight": "Starlight",
    "visor": "Visor",
    "rainbow_circle": "Rainbow Circle",
    "vertical_rainbow": "Vertical Rainbow",
    "blooming": "Blooming",
    "reactive": "Reactive",
    "reactive_ripple": "Reactive Ripple",
    "reactive_line": "Reactive Line",
    "custom": "Custom",
    "off": "Off",
}

# Ordem visual ABNT2 usada pelo controlador EVision no modo Custom. O OpenRGB
# aceita uma lista de cores e distribui uma cor por LED na ordem do dispositivo.
K552_KEY_ORDER = (
    "Esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "PrtSc", "ScrLk", "Pause",
    "'", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "⌫", "Ins", "Home", "PgUp",
    "Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "´", "[", "Enter", "Del", "End", "PgDn",
    "Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Ç", "~", "]", "Enter↵",
    "Shift", "\\", "Z", "X", "C", "V", "B", "N", "M", ",", ".", ";", "Shift R", "↑",
    "Ctrl", "Super", "Alt", "Espaço", "AltGr", "Fn", "Menu", "Ctrl R", "←", "↓", "→",
)


class KeyboardError(RuntimeError):
    pass


@dataclass(slots=True)
class KeyboardProfile:
    name: str = "Principal"
    mode: str = "custom"
    color: str = "9b5cff"
    brightness: int = 85
    speed: int = 50
    direction: str = "right"
    key_colors: dict[str, str] = field(default_factory=dict)
    key_actions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KeyboardStatus:
    connected: bool
    accessible: bool
    openrgb_path: str | None
    hidraw_paths: tuple[str, ...]


def _devices() -> list[Path]:
    result: list[Path] = []
    for path in Path("/sys/bus/usb/devices").glob("*"):
        try:
            if (
                (path / "idVendor").read_text().strip().lower() == VID
                and (path / "idProduct").read_text().strip().lower() == PID
            ):
                result.append(path)
        except (FileNotFoundError, PermissionError):
            continue
    return result


def keyboard_status() -> KeyboardStatus:
    devices = _devices()
    hidraw: list[Path] = []
    for device in devices:
        hidraw.extend(Path("/sys/class/hidraw").glob("hidraw*"))
        break
    paths = tuple(
        str(Path("/dev") / path.name)
        for path in hidraw
        if _hidraw_matches(path)
    )
    preview = os.environ.get("REDRAGON_PREVIEW") == "1"
    return KeyboardStatus(
        connected=bool(devices) or preview,
        accessible=preview or any(os.access(path, os.R_OK | os.W_OK) for path in paths),
        openrgb_path=shutil.which("openrgb") or ("openrgb" if preview else None),
        hidraw_paths=paths,
    )


def _hidraw_matches(path: Path) -> bool:
    try:
        target = path.resolve()
        current = target
        while current != current.parent:
            vendor = current / "idVendor"
            product = current / "idProduct"
            if vendor.exists() and product.exists():
                return vendor.read_text().strip().lower() == VID and product.read_text().strip().lower() == PID
            current = current.parent
    except (FileNotFoundError, PermissionError):
        pass
    return False


def profiles_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "redragon-control" / "keyboard.json"


def load_keyboard_profiles(path: Path | None = None) -> tuple[list[KeyboardProfile], int]:
    payload = json.loads((path or profiles_path()).read_text(encoding="utf-8"))
    profiles = [KeyboardProfile(**item) for item in payload["profiles"]]
    if not profiles:
        raise ValueError("Nenhum perfil de teclado salvo.")
    active = int(payload.get("active", 0))
    return profiles, max(0, min(active, len(profiles) - 1))


def save_keyboard_profiles(
    profiles: list[KeyboardProfile], active: int, path: Path | None = None
) -> None:
    destination = path or profiles_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"version": 1, "active": active, "profiles": [asdict(profile) for profile in profiles]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)


def default_keyboard_profiles() -> list[KeyboardProfile]:
    return [
        KeyboardProfile(name="Principal"),
        KeyboardProfile(name="Jogos", mode="reactive_ripple", color="ff304f", speed=70),
        KeyboardProfile(name="Trabalho", mode="static", color="3b82f6", brightness=55),
    ]


def _run_openrgb(*args: str, timeout: int = 20) -> str:
    path = shutil.which("openrgb")
    if os.environ.get("REDRAGON_PREVIEW") == "1":
        return ""
    if not path:
        raise KeyboardError("OpenRGB não está instalado.")
    result = subprocess.run(
        [path, "--noautoconnect", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise KeyboardError((result.stderr or result.stdout).strip() or "Falha ao configurar o teclado.")
    return result.stdout


def _device_index() -> int:
    output = _run_openrgb("--list-devices")
    # OpenRGB imprime "N: Evision RGB Keyboard". A busca por VID/PID em
    # --list-detailed varia entre versões, por isso o nome é o fallback estável.
    for line in output.splitlines():
        match = re.match(r"\s*(\d+):\s*(.*(?:Evision|RGB Keyboard).*)", line, re.I)
        if match:
            return int(match.group(1))
    if os.environ.get("REDRAGON_PREVIEW") == "1":
        return 0
    raise KeyboardError("O teclado S118/K552 não apareceu na lista do OpenRGB.")


def apply_keyboard(profile: KeyboardProfile) -> None:
    if profile.mode not in KEYBOARD_MODES:
        raise ValueError("Efeito de teclado inválido.")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", profile.color):
        raise ValueError("Cor do teclado inválida.")
    index = _device_index()
    colors = profile.color.upper()
    if profile.mode == "custom":
        colors = ",".join(
            profile.key_colors.get(key, profile.color).upper()
            for key in K552_KEY_ORDER
        )
    args = [
        "--device", str(index),
        "--mode", OPENRGB_MODES[profile.mode],
        "--color", colors,
        "--brightness", str(max(0, min(100, profile.brightness))),
        "--speed", str(max(0, min(100, profile.speed))),
    ]
    _run_openrgb(*args, timeout=30)
