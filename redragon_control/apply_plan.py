from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplyPlan:
    mouse: bool
    keyboard: bool
    mouse_settings: bool
    macros: bool


def build_apply_plan(
    *,
    mouse_dirty: bool,
    keyboard_dirty: bool,
    macros_dirty: bool,
    mouse_dpi_enabled: list[bool],
) -> ApplyPlan:
    """Describe exactly which hardware backends need to be called.

    Macros are stored in the M711's internal slots, so changing a macro is a
    mouse operation even when no DPI, polling-rate or lighting field changed.
    Mouse validation must not block an unrelated keyboard-only operation.
    """

    apply_mouse = mouse_dirty or macros_dirty
    if apply_mouse and not any(mouse_dpi_enabled):
        raise ValueError("Ative ao menos um nível de DPI.")
    return ApplyPlan(
        mouse=apply_mouse,
        keyboard=keyboard_dirty,
        mouse_settings=mouse_dirty,
        macros=macros_dirty,
    )
