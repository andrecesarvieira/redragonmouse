from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from io import StringIO
import re


DPI_VALUES = tuple(range(100, 5001, 100)) + tuple(range(5200, 10001, 200))
DPI_CODE_BYTES = (
    0x02, 0x04, 0x06, 0x08, 0x0B, 0x0D, 0x0F, 0x12, 0x14, 0x16,
    0x19, 0x1B, 0x1D, 0x20, 0x22, 0x24, 0x27, 0x29, 0x2B, 0x2E,
    0x30, 0x32, 0x34, 0x37, 0x39, 0x3B, 0x3E, 0x40, 0x42, 0x45,
    0x47, 0x49, 0x4C, 0x4E, 0x50, 0x53, 0x55, 0x57, 0x5A, 0x5C,
    0x5E, 0x61, 0x63, 0x65, 0x68, 0x6A, 0x6C, 0x6F, 0x71, 0x73,
)
DPI_RAW_CODES = {
    (code, 0): dpi for code, dpi in zip(DPI_CODE_BYTES, range(100, 5001, 100))
} | {
    (code, 1): dpi for code, dpi in zip(DPI_CODE_BYTES[25:], range(5200, 10001, 200))
}
REPORT_RATES = (125, 250, 500, 1000)
LIGHT_MODES = (
    "static",
    "breathing",
    "breathing_rainbow",
    "rainbow",
    "wave",
    "alternating",
    "reactive",
    "reactive_button",
    "flashing",
    "random",
    "off",
)

BUTTON_NAMES = (
    "button_left",
    "button_right",
    "button_middle",
    "button_backward",
    "button_forward",
    "button_dpi_up",
    "button_dpi_down",
    "button_lightmode",
    "scroll_up",
    "scroll_down",
)

DEFAULT_BUTTON_MAPPINGS = {
    "button_left": "left",
    "button_right": "right",
    "button_middle": "middle",
    "button_backward": "backward",
    "button_forward": "forward",
    "button_dpi_up": "dpi+",
    "button_dpi_down": "dpi-",
    "button_lightmode": "led_mode_switch",
    "scroll_up": "scroll_up",
    "scroll_down": "scroll_down",
}


@dataclass(slots=True)
class Profile:
    dpi: list[int] = field(default_factory=lambda: [500, 1000, 2000, 3000, 5000])
    dpi_enabled: list[bool] = field(default_factory=lambda: [True] * 5)
    report_rate: int = 1000
    light_mode: str = "static"
    color: str = "ff2020"
    brightness: int = 3
    speed: int = 4
    scroll_speed: int = 1
    button_mappings: dict[str, str] = field(default_factory=lambda: DEFAULT_BUTTON_MAPPINGS.copy())


def default_profiles() -> list[Profile]:
    return [Profile() for _ in range(5)]


def validate_profiles(profiles: list[Profile]) -> None:
    if len(profiles) != 5:
        raise ValueError("O M711 requer exatamente cinco perfis.")
    for number, profile in enumerate(profiles, 1):
        if len(profile.dpi) != 5 or len(profile.dpi_enabled) != 5:
            raise ValueError(f"O perfil {number} requer cinco níveis de DPI.")
        if not any(profile.dpi_enabled):
            raise ValueError(f"Ative ao menos um nível de DPI no perfil {number}.")
        if any(value not in DPI_VALUES for value in profile.dpi):
            raise ValueError(f"Há um DPI inválido no perfil {number}.")
        if profile.report_rate not in REPORT_RATES:
            raise ValueError(f"Polling rate inválido no perfil {number}.")
        if profile.light_mode not in LIGHT_MODES:
            raise ValueError(f"Efeito de luz inválido no perfil {number}.")
        if len(profile.color) != 6 or any(c not in "0123456789abcdefABCDEF" for c in profile.color):
            raise ValueError(f"Cor RGB inválida no perfil {number}.")
        if profile.brightness not in range(1, 4) or profile.speed not in range(1, 9):
            raise ValueError(f"Brilho ou velocidade inválidos no perfil {number}.")
        if profile.scroll_speed not in range(1, 64):
            raise ValueError(f"Velocidade de rolagem inválida no perfil {number}.")
        if set(profile.button_mappings) != set(BUTTON_NAMES):
            raise ValueError(f"Mapeamento de botões incompleto no perfil {number}.")
        if any(not value.strip() for value in profile.button_mappings.values()):
            raise ValueError(f"Mapeamento de botão vazio no perfil {number}.")


def serialize(profiles: list[Profile], active_profile: int | None = None) -> str:
    """Gera o INI aceito pelo backend mouse_m908."""
    validate_profiles(profiles)
    lines = ["# Gerado pelo Redragon Control para o M711 Cobra", ""]
    if active_profile is not None:
        if active_profile not in range(1, 6):
            raise ValueError("Perfil ativo inválido.")
        lines.extend([f"# Currently active profile: {active_profile}", ""])
    for number, profile in enumerate(profiles, 1):
        lines.extend(
            [
                f"[profile{number}]",
                f"lightmode={profile.light_mode}",
                f"color={profile.color.lower()}",
                f"brightness={profile.brightness}",
                f"speed={profile.speed}",
                f"scrollspeed={profile.scroll_speed:x}",
                f"report_rate={profile.report_rate}",
            ]
        )
        for level, (dpi, enabled) in enumerate(zip(profile.dpi, profile.dpi_enabled), 1):
            lines.append(f"dpi{level}_enable={int(enabled)}")
            lines.append(f"dpi{level}={dpi}")
        for button in BUTTON_NAMES:
            lines.append(f"{button}={profile.button_mappings[button]}")
        lines.append("")
    return "\n".join(lines)


def parse_active_profile(text: str) -> int:
    match = re.search(r"^#\s*Currently active profile:\s*([1-5])\s*$", text, flags=re.MULTILINE)
    return int(match.group(1)) if match else 1


def parse(text: str) -> list[Profile]:
    parser = ConfigParser(interpolation=None)
    parser.read_file(StringIO(text))
    profiles = default_profiles()
    for index, profile in enumerate(profiles, 1):
        section_name = f"profile{index}"
        if not parser.has_section(section_name):
            continue
        section = parser[section_name]
        profile.report_rate = section.getint("report_rate", fallback=profile.report_rate)
        profile.light_mode = section.get("lightmode", fallback=profile.light_mode)
        profile.color = section.get("color", fallback=profile.color).lstrip("#")
        profile.brightness = section.getint("brightness", fallback=profile.brightness)
        try:
            profile.scroll_speed = int(section.get("scrollspeed", fallback="1"), 16)
        except ValueError:
            profile.scroll_speed = 1
        speed = section.getint("speed", fallback=profile.speed)
        # O leitor do M711 às vezes devolve zero porque consulta um byte
        # diferente daquele usado na gravação. Preserve o fallback nesse caso.
        if speed in range(1, 9):
            profile.speed = speed
        for level in range(5):
            raw_dpi = section.get(f"dpi{level + 1}", fallback=str(profile.dpi[level]))
            match = re.fullmatch(r"X(\d+)Y(\d+)", raw_dpi, flags=re.IGNORECASE)
            if match:
                dpi_x, dpi_y = map(int, match.groups())
                if dpi_x != dpi_y:
                    raise ValueError(
                        f"O perfil {index}, nível {level + 1}, usa DPI X/Y diferentes; "
                        "esta versão da interface ainda não edita eixos separadamente."
                    )
                profile.dpi[level] = dpi_x
            elif raw_match := re.fullmatch(r"0x([0-9a-fA-F]{8})", raw_dpi):
                raw = raw_match.group(1)
                code = (int(raw[0:2], 16), int(raw[2:4], 16))
                try:
                    profile.dpi[level] = DPI_RAW_CODES[code]
                except KeyError as error:
                    raise ValueError(
                        f"O perfil {index}, nível {level + 1}, retornou o DPI bruto desconhecido {raw_dpi}."
                    ) from error
            elif raw_dpi.isdigit():
                profile.dpi[level] = int(raw_dpi)
            else:
                raise ValueError(
                    f"O mouse retornou um DPI bruto não reconhecido no perfil {index}, nível {level + 1}: {raw_dpi}"
                )
            profile.dpi_enabled[level] = section.getboolean(
                f"dpi{level + 1}_enable", fallback=profile.dpi_enabled[level]
            )
        for button in BUTTON_NAMES:
            profile.button_mappings[button] = section.get(
                button, fallback=profile.button_mappings[button]
            )
    validate_profiles(profiles)
    return profiles
