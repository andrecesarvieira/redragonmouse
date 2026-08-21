from __future__ import annotations

import json
import os
import re
import select
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

KEYBOARD_SPEED_MODES = frozenset(
    {
        "color_wave",
        "color_wave_short",
        "color_wheel",
        "spectrum_cycle",
        "breathing",
        "hurricane",
        "accumulate",
        "starlight",
        "vertical_rainbow",
        "blooming",
        "reactive",
        "reactive_ripple",
        "reactive_line",
    }
)
KEYBOARD_DIRECTION_MODES = {
    "color_wave": ("left", "right"),
    "color_wave_short": ("left", "right"),
    "color_wheel": ("left", "right"),
    "vertical_rainbow": ("up", "down"),
}

# Valores do protocolo HID do controlador EVision/Sonix. A implementação é
# compatível com o protocolo publicado pelo projeto GPL OpenRGB, mas conversa
# diretamente com o hidraw e não executa nem depende do OpenRGB.
EVISION_MODES = {
    "color_wave_short": 0x01,
    "color_wave": 0x02,
    "color_wheel": 0x03,
    "spectrum_cycle": 0x04,
    "breathing": 0x05,
    "static": 0x06,
    "reactive": 0x07,
    "reactive_ripple": 0x08,
    "reactive_line": 0x09,
    "starlight": 0x0A,
    "blooming": 0x0B,
    "vertical_rainbow": 0x0C,
    "hurricane": 0x0D,
    "accumulate": 0x0E,
    "visor": 0x10,
    "rainbow_circle": 0x12,
    "custom": 0x14,
    "off": 0x06,
}

K552_KEY_ORDER = (
    "Esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "PrtSc", "ScrLk", "Pause",
    "'", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "⌫", "Ins", "Home", "PgUp",
    "Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "´", "[", "Enter", "Del", "End", "PgDn",
    "Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Ç", "~", "]", "Enter↵",
    "Shift", "\\", "Z", "X", "C", "V", "B", "N", "M", ",", ".", ";", "Shift R", "↑",
    "Ctrl", "Super", "Alt", "Espaço", "AltGr", "Fn", "Menu", "Ctrl R", "←", "↓", "→",
)

# Posições dos LEDs no buffer EVision de 126 LEDs. Os espaços correspondem
# às lacunas da matriz e às posições de navegação do layout TKL ABNT2.
K552_LED_INDICES = (
    *range(0, 13), 14, 15, 16,
    *range(21, 38),
    *range(42, 59),
    *range(63, 77),
    84, 85, *range(86, 96), 97, 99,
    105, 106, 107, 108, 109, 110, 111, 113, 119, 120, 121,
)
K552_LED_INDEX = dict(zip(K552_KEY_ORDER, K552_LED_INDICES, strict=True))

REPORT_SIZE = 64
COLOR_PACKET_SIZE = 0x36
COLOR_DATA_SIZE = 126 * 3
REPORT_ID = 0x04
COMMAND_SET_PARAMETER = 0x06
COMMAND_WRITE_COLORS = 0x11
CONTROL_USAGE_DESCRIPTOR = b"\x06\x1c\xff"


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


def _hidraw_matches(path: Path) -> bool:
    try:
        current = path.resolve()
        while current != current.parent:
            vendor = current / "idVendor"
            product = current / "idProduct"
            if vendor.exists() and product.exists():
                return (
                    vendor.read_text().strip().lower() == VID
                    and product.read_text().strip().lower() == PID
                )
            current = current.parent
    except (FileNotFoundError, PermissionError):
        pass
    return False


def _is_control_interface(path: Path) -> bool:
    try:
        descriptor = (path / "device" / "report_descriptor").read_bytes()
        return CONTROL_USAGE_DESCRIPTOR in descriptor and b"\x85\x04" in descriptor
    except (FileNotFoundError, PermissionError):
        return False


def _control_hidraw_paths() -> tuple[str, ...]:
    return tuple(
        str(Path("/dev") / path.name)
        for path in Path("/sys/class/hidraw").glob("hidraw*")
        if _hidraw_matches(path) and _is_control_interface(path)
    )


def keyboard_status() -> KeyboardStatus:
    preview = os.environ.get("REDRAGON_PREVIEW") == "1"
    paths = _control_hidraw_paths()
    return KeyboardStatus(
        connected=bool(_devices()) or preview,
        accessible=preview or any(os.access(path, os.R_OK | os.W_OK) for path in paths),
        hidraw_paths=paths,
    )


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


def _checksum(packet: bytearray) -> None:
    checksum = sum(packet[3:]) & 0xFFFF
    packet[1] = checksum & 0xFF
    packet[2] = checksum >> 8


def _parameter_packet(data: bytes, parameter: int = 0) -> bytes:
    if len(data) > REPORT_SIZE - 8:
        raise ValueError("Parâmetro HID do teclado excede o tamanho permitido.")
    packet = bytearray(REPORT_SIZE)
    packet[0] = REPORT_ID
    packet[3] = COMMAND_SET_PARAMETER
    packet[4] = len(data)
    packet[5] = parameter
    packet[8:8 + len(data)] = data
    _checksum(packet)
    return bytes(packet)


def _color_packet(data: bytes, offset: int) -> bytes:
    if len(data) > COLOR_PACKET_SIZE:
        raise ValueError("Pacote RGB do teclado excede o tamanho permitido.")
    packet = bytearray(REPORT_SIZE)
    packet[0] = REPORT_ID
    packet[3] = COMMAND_WRITE_COLORS
    packet[4] = len(data)
    packet[5] = offset & 0xFF
    packet[6] = offset >> 8
    packet[8:8 + len(data)] = data
    _checksum(packet)
    return bytes(packet)


def _rgb(value: str) -> bytes:
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Cor do teclado inválida.")
    return bytes.fromhex(value)


def normalize_keyboard_brightness(percent: int) -> int:
    """Normaliza o percentual para um dos cinco níveis nativos (0, 25…100)."""
    clamped = max(0, min(100, percent))
    return min(4, (clamped + 12) // 25) * 25


def normalize_keyboard_speed(percent: int) -> int:
    """Normaliza o percentual para um dos seis níveis nativos (0, 20…100)."""
    clamped = max(0, min(100, percent))
    return min(5, (clamped + 10) // 20) * 20


def _mode_parameters(profile: KeyboardProfile) -> bytes:
    brightness = normalize_keyboard_brightness(profile.brightness) // 25
    # O protocolo EVision usa atraso: 5 é o mais lento e 0 o mais rápido.
    speed = 5 - normalize_keyboard_speed(profile.speed) // 20
    direction = {"left": 0, "right": 1, "up": 2, "down": 3}.get(profile.direction)
    if direction is None:
        raise ValueError("Direção do teclado inválida.")
    color = _rgb(profile.color)
    mode = EVISION_MODES[profile.mode]
    random = 1 if profile.mode in {"blooming", "rainbow_circle"} else 0
    if profile.mode == "off":
        brightness = 0
    return bytes((mode, brightness, speed, direction, random, *color))


def _custom_color_data(profile: KeyboardProfile) -> bytes:
    default = _rgb(profile.color)
    data = bytearray(default * 126)
    for key, color in profile.key_colors.items():
        led_index = K552_LED_INDEX.get(key)
        if led_index is not None:
            start = led_index * 3
            data[start:start + 3] = _rgb(color)
    return bytes(data)


def _packets_for_profile(profile: KeyboardProfile) -> list[bytes]:
    if profile.mode not in KEYBOARD_MODES:
        raise ValueError("Efeito de teclado inválido.")
    packets = [_parameter_packet(_mode_parameters(profile))]
    if profile.mode == "custom":
        colors = _custom_color_data(profile)
        packets.extend(
            _color_packet(colors[offset:offset + COLOR_PACKET_SIZE], offset)
            for offset in range(0, COLOR_DATA_SIZE, COLOR_PACKET_SIZE)
        )
    return packets


def _exchange(fd: int, packet: bytes, timeout: float = 2.0) -> None:
    written = os.write(fd, packet)
    if written != len(packet):
        raise KeyboardError("O teclado recebeu um pacote HID incompleto.")
    readable, _, _ = select.select([fd], [], [], timeout)
    if not readable:
        raise KeyboardError("O teclado não respondeu ao comando HID.")
    response = os.read(fd, REPORT_SIZE)
    if not response:
        raise KeyboardError("O teclado encerrou a comunicação HID.")


def _send_packets(packets: list[bytes], device_path: str | None = None) -> None:
    paths = (device_path,) if device_path else _control_hidraw_paths()
    if not paths:
        raise KeyboardError("Interface HID do teclado S118/K552 não encontrada.")
    try:
        fd = os.open(paths[0], os.O_RDWR | os.O_CLOEXEC)
    except PermissionError as error:
        raise KeyboardError("Sem permissão para acessar a interface HID do teclado.") from error
    except OSError as error:
        raise KeyboardError(f"Não foi possível abrir o teclado: {error}") from error
    try:
        for packet in packets:
            _exchange(fd, packet)
    finally:
        os.close(fd)


def apply_keyboard(profile: KeyboardProfile) -> None:
    if os.environ.get("REDRAGON_PREVIEW") == "1":
        return
    _send_packets(_packets_for_profile(profile))
