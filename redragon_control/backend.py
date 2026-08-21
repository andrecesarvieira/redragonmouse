from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Profile, parse, parse_active_profile, serialize


VID = "04d9"
PID = "fc30"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BackendError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceStatus:
    connected: bool
    accessible: bool
    backend_path: str | None
    usb_path: str | None


def find_backend() -> str | None:
    override = os.environ.get("REDRAGON_BACKEND")
    candidates = [
        override,
        str(PROJECT_ROOT / ".local/bin/mouse_m908"),
        "/usr/libexec/redragon-control/mouse_m908",
        shutil.which("mouse_m908"),
    ]
    return next((candidate for candidate in candidates if candidate and os.access(candidate, os.X_OK)), None)


def _usb_device_paths() -> list[Path]:
    devices: list[Path] = []
    for path in Path("/sys/bus/usb/devices").glob("*"):
        try:
            if (path / "idVendor").read_text().strip().lower() == VID and (path / "idProduct").read_text().strip().lower() == PID:
                devices.append(path)
        except (FileNotFoundError, PermissionError):
            pass
    return devices


def device_status() -> DeviceStatus:
    devices = _usb_device_paths()
    usb_node: Path | None = None
    if devices:
        try:
            bus = int((devices[0] / "busnum").read_text())
            dev = int((devices[0] / "devnum").read_text())
            usb_node = Path(f"/dev/bus/usb/{bus:03d}/{dev:03d}")
        except (FileNotFoundError, ValueError):
            pass
    return DeviceStatus(
        connected=bool(devices),
        accessible=bool(usb_node and os.access(usb_node, os.R_OK | os.W_OK)),
        backend_path=find_backend(),
        usb_path=str(usb_node) if usb_node else None,
    )


def _run(*arguments: str, timeout: int = 20) -> str:
    backend = find_backend()
    if not backend:
        raise BackendError("Backend mouse_m908 não instalado. Execute scripts/setup-fedora.sh.")
    try:
        result = subprocess.run(
            [backend, "--model", "711", *arguments],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise BackendError("O mouse não respondeu dentro do tempo esperado.") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise BackendError(detail or f"O backend terminou com código {result.returncode}.")
    return result.stdout


def read_profiles() -> list[Profile]:
    return parse(_run("--read", "-"))


def read_configuration() -> tuple[list[Profile], int]:
    output = _run("--read", "-")
    return parse(output), parse_active_profile(output)


def apply_profiles(profiles: list[Profile], active_profile: int, macro_text: str = "") -> None:
    if active_profile not in range(1, 6):
        raise ValueError("Perfil ativo inválido.")
    config = serialize(profiles)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ini", encoding="utf-8", delete=False) as handle:
            handle.write(config)
            if macro_text:
                handle.write("\n")
                handle.write(macro_text)
                handle.write("\n")
            temporary_name = handle.name
        # O mesmo arquivo contém os 15 slots de macro. Passá-lo também em
        # --macro evita que o backend grave apenas perfis e deixe macros antigas.
        _run(
            "--config", temporary_name,
            "--macro", temporary_name,
            "--profile", str(active_profile),
            timeout=50,
        )
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
