from __future__ import annotations

import threading
from copy import deepcopy

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .backend import BackendError, apply_profiles, device_status, read_configuration
from .config import DPI_VALUES, LIGHT_MODES, REPORT_RATES, Profile, default_profiles
from .persistence import load_state, save_state


LIGHT_LABELS = {
    "static": "Estática",
    "breathing": "Respiração",
    "breathing_rainbow": "Respiração arco-íris",
    "rainbow": "Arco-íris",
    "wave": "Onda",
    "alternating": "Alternada",
    "reactive": "Reativa",
    "reactive_button": "Reativa ao botão",
    "flashing": "Piscante",
    "random": "Aleatória",
    "off": "Desligada",
}


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Redragon Control")
        self.set_default_size(720, 720)
        try:
            self.profiles, active_profile = load_state()
            self.profile_index = active_profile - 1
            self._profiles_loaded = True
        except (OSError, ValueError):
            self.profiles = default_profiles()
            self.profile_index = 0
            self._profiles_loaded = False
        self._loading = False
        self._busy = False
        self._ready = False
        self._dirty = False
        self._dpi_rows: list[tuple[Gtk.Switch, Gtk.DropDown]] = []

        overlay = Adw.ToastOverlay()
        self.set_content(overlay)
        self.toast_overlay = overlay

        toolbar = Adw.ToolbarView()
        overlay.set_child(toolbar)
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        self.read_button = Gtk.Button(label="Ler do mouse")
        self.read_button.connect("clicked", self._on_read)
        header.pack_start(self.read_button)
        self.apply_button = Gtk.Button(label="Aplicar")
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.connect("clicked", self._on_apply)
        header.pack_end(self.apply_button)

        page = Adw.PreferencesPage()
        toolbar.set_content(page)

        device_group = Adw.PreferencesGroup(title="Dispositivo")
        self.device_row = Adw.ActionRow(title="Redragon M711 Cobra", subtitle="Verificando…")
        self.status_icon = Gtk.Image.new_from_icon_name("content-loading-symbolic")
        self.device_row.add_prefix(self.status_icon)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER)
        refresh.add_css_class("flat")
        refresh.connect("clicked", lambda *_: self._refresh_status())
        self.device_row.add_suffix(refresh)
        device_group.add(self.device_row)
        page.add(device_group)

        profile_group = Adw.PreferencesGroup(
            title="Perfil",
            description="As alterações são gravadas na memória interna. Neste MVP, mapeamentos personalizados de botões podem voltar ao padrão.",
        )
        self.profile_dropdown = Gtk.DropDown.new_from_strings([f"Perfil {i}" for i in range(1, 6)])
        self.profile_dropdown.set_selected(self.profile_index)
        self.profile_dropdown.connect("notify::selected", self._on_profile_changed)
        profile_row = Adw.ActionRow(title="Perfil ativo")
        profile_row.add_suffix(self.profile_dropdown)
        profile_group.add(profile_row)
        page.add(profile_group)

        dpi_group = Adw.PreferencesGroup(title="Sensibilidade", description="O M711 oferece cinco estágios selecionáveis pelo botão DPI.")
        for level in range(5):
            row = Adw.ActionRow(title=f"Nível {level + 1}")
            enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
            enabled.connect("notify::active", self._controls_changed)
            values = Gtk.StringList.new([str(value) for value in DPI_VALUES])
            dropdown = Gtk.DropDown(model=values, valign=Gtk.Align.CENTER)
            dropdown.set_enable_search(True)
            dropdown.connect("notify::selected", self._controls_changed)
            row.add_suffix(enabled)
            row.add_suffix(dropdown)
            row.set_activatable_widget(enabled)
            dpi_group.add(row)
            self._dpi_rows.append((enabled, dropdown))
        page.add(dpi_group)

        performance_group = Adw.PreferencesGroup(title="Desempenho")
        self.rate_dropdown = Gtk.DropDown.new_from_strings([f"{rate} Hz" for rate in REPORT_RATES])
        self.rate_dropdown.connect("notify::selected", self._controls_changed)
        rate_row = Adw.ActionRow(title="Polling rate", subtitle="Frequência de comunicação USB")
        rate_row.add_suffix(self.rate_dropdown)
        performance_group.add(rate_row)
        page.add(performance_group)

        light_group = Adw.PreferencesGroup(title="Iluminação")
        self.light_dropdown = Gtk.DropDown.new_from_strings([LIGHT_LABELS[mode] for mode in LIGHT_MODES])
        self.light_dropdown.connect("notify::selected", self._controls_changed)
        light_row = Adw.ActionRow(title="Efeito")
        light_row.add_suffix(self.light_dropdown)
        light_group.add(light_row)

        self.color_button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Cor do mouse"))
        self.color_button.connect("notify::rgba", self._controls_changed)
        color_row = Adw.ActionRow(title="Cor")
        color_row.add_suffix(self.color_button)
        light_group.add(color_row)

        self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 3, 1)
        self.brightness.set_size_request(220, -1)
        self.brightness.set_draw_value(True)
        self.brightness.connect("value-changed", self._controls_changed)
        brightness_row = Adw.ActionRow(title="Brilho")
        brightness_row.add_suffix(self.brightness)
        light_group.add(brightness_row)

        self.speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 8, 1)
        self.speed.set_size_request(220, -1)
        self.speed.set_draw_value(True)
        self.speed.connect("value-changed", self._controls_changed)
        speed_row = Adw.ActionRow(title="Velocidade do efeito")
        speed_row.add_suffix(self.speed)
        light_group.add(speed_row)
        page.add(light_group)

        self._load_profile(self.profile_index)
        self._refresh_status()
        if self._ready and not self._profiles_loaded:
            GLib.idle_add(self._read_from_mouse, False)

    def _toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=4))

    def _refresh_status(self) -> None:
        status = device_status()
        if not status.connected:
            subtitle, icon = "Desconectado", "dialog-warning-symbolic"
        elif not status.accessible:
            subtitle, icon = "Conectado — falta permissão USB (execute a configuração)", "changes-prevent-symbolic"
        elif not status.backend_path:
            subtitle, icon = "Conectado — backend não instalado", "dialog-warning-symbolic"
        else:
            subtitle, icon = "Conectado e pronto", "emblem-ok-symbolic"
        self.device_row.set_subtitle(subtitle)
        self.status_icon.set_from_icon_name(icon)
        self._ready = status.connected and status.accessible and bool(status.backend_path)
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        self.read_button.set_sensitive(self._ready and not self._busy)
        self.apply_button.set_sensitive(
            self._ready and not self._busy and self._profiles_loaded and self._dirty
        )

    def _store_profile(self) -> None:
        if self._loading:
            return
        profile = self.profiles[self.profile_index]
        profile.dpi_enabled = [switch.get_active() for switch, _ in self._dpi_rows]
        profile.dpi = [DPI_VALUES[dropdown.get_selected()] for _, dropdown in self._dpi_rows]
        profile.report_rate = REPORT_RATES[self.rate_dropdown.get_selected()]
        profile.light_mode = LIGHT_MODES[self.light_dropdown.get_selected()]
        rgba = self.color_button.get_rgba()
        profile.color = "{:02x}{:02x}{:02x}".format(round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))
        profile.brightness = round(self.brightness.get_value())
        profile.speed = round(self.speed.get_value())

    def _load_profile(self, index: int) -> None:
        self._loading = True
        self.profile_index = index
        profile = self.profiles[index]
        for level, (switch, dropdown) in enumerate(self._dpi_rows):
            switch.set_active(profile.dpi_enabled[level])
            dropdown.set_selected(DPI_VALUES.index(profile.dpi[level]))
        self.rate_dropdown.set_selected(REPORT_RATES.index(profile.report_rate))
        self.light_dropdown.set_selected(LIGHT_MODES.index(profile.light_mode))
        rgba = Gdk.RGBA()
        rgba.parse(f"#{profile.color}")
        self.color_button.set_rgba(rgba)
        self.brightness.set_value(profile.brightness)
        self.speed.set_value(profile.speed)
        self._loading = False

    def _controls_changed(self, *_args) -> None:
        if self._loading:
            return
        self._store_profile()
        self._dirty = True
        self._update_action_buttons()

    def _on_profile_changed(self, dropdown, _param) -> None:
        if self._loading:
            return
        self._store_profile()
        self._load_profile(dropdown.get_selected())
        self._dirty = True
        self._update_action_buttons()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_action_buttons()
        self.set_cursor(Gdk.Cursor.new_from_name("wait") if busy else None)

    def _background(self, operation, success_message: str | None, update_profiles: bool = False) -> None:
        self._set_busy(True)

        def worker():
            try:
                result = operation()
                GLib.idle_add(done, result, None)
            except Exception as error:  # boundary between worker and UI
                GLib.idle_add(done, None, error)

        def done(result, error):
            self._set_busy(False)
            if error:
                message = str(error) if isinstance(error, (BackendError, ValueError)) else "Falha inesperada ao comunicar com o mouse."
                self._toast(message)
            else:
                if update_profiles:
                    self.profiles, active_profile = result
                    self._profiles_loaded = True
                    self._dirty = False
                    self._loading = True
                    self.profile_dropdown.set_selected(active_profile - 1)
                    self._loading = False
                    self._load_profile(active_profile - 1)
                    try:
                        save_state(self.profiles, active_profile)
                    except OSError:
                        self._toast("Configuração aplicada, mas não foi possível salvar o estado local.")
                if success_message:
                    self._toast(success_message)
            self._refresh_status()
            return GLib.SOURCE_REMOVE

        threading.Thread(target=worker, daemon=True).start()

    def _on_read(self, _button) -> None:
        self._read_from_mouse(True)

    def _read_from_mouse(self, show_message: bool) -> bool:
        self._background(
            read_configuration,
            "Configurações lidas do mouse." if show_message else None,
            update_profiles=True,
        )
        return GLib.SOURCE_REMOVE

    def _on_apply(self, _button) -> None:
        self._store_profile()
        if not any(self.profiles[self.profile_index].dpi_enabled):
            self._toast("Ative ao menos um nível de DPI neste perfil.")
            return
        snapshot = deepcopy(self.profiles)
        active = self.profile_index + 1

        def apply_and_save():
            apply_profiles(snapshot, active)
            return snapshot, active

        self._background(
            apply_and_save,
            "Configurações aplicadas e salvas.",
            update_profiles=True,
        )


class RedragonApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.redragon.Control")

    def do_activate(self):
        window = self.props.active_window or MainWindow(application=self)
        window.present()


def main() -> int:
    return RedragonApplication().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
