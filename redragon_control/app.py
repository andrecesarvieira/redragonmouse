from __future__ import annotations

import os
import threading
from copy import deepcopy

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .apply_plan import build_apply_plan
from .backend import BackendError, apply_profiles, device_status, read_configuration
from .config import BUTTON_NAMES, DPI_VALUES, LIGHT_MODES, REPORT_RATES, default_profiles, mouse_speed_from_ui, mouse_speed_to_ui
from .keyboard import KEYBOARD_DIRECTION_MODES, KEYBOARD_SPEED_MODES, KeyboardError, KEYBOARD_MODES, apply_keyboard, default_keyboard_profiles, keyboard_status, load_keyboard_profiles, normalize_keyboard_brightness, normalize_keyboard_speed, save_keyboard_profiles
from .macros import default_macros, load_macros, save_macros, serialize_macros
from .persistence import load_state, save_state

LIGHT_LABELS = {"static": "Estática", "breathing": "Respiração", "breathing_rainbow": "Respiração arco-íris", "rainbow": "Arco-íris", "wave": "Onda", "alternating": "Alternada", "reactive": "Reativa", "reactive_button": "Reativa ao botão", "flashing": "Piscante", "random": "Aleatória", "off": "Desligada"}
KEYBOARD_MODE_LABELS = {"static": "Cor estática", "color_wave": "Onda de cores", "color_wave_short": "Onda curta", "color_wheel": "Roda de cores", "spectrum_cycle": "Ciclo de espectro", "breathing": "Respiração", "hurricane": "Furacão", "accumulate": "Acumular", "starlight": "Luz estelar", "visor": "Visor", "rainbow_circle": "Círculo arco-íris", "vertical_rainbow": "Arco-íris vertical", "blooming": "Florescer", "reactive": "Reativo", "reactive_ripple": "Ondulação reativa", "reactive_line": "Linha reativa", "custom": "Personalizado por tecla", "off": "Desligado"}
BUTTON_LABELS = {"button_left": "Botão esquerdo", "button_right": "Botão direito", "button_middle": "Clique do scroll", "button_backward": "Voltar", "button_forward": "Avançar", "button_dpi_up": "DPI +", "button_dpi_down": "DPI −", "button_lightmode": "Alternar iluminação", "scroll_up": "Scroll para cima", "scroll_down": "Scroll para baixo"}
NAVIGATION = (("Visão geral", "overview", "view-grid-symbolic"), ("Mouse M711", "mouse", "input-mouse-symbolic"), ("Teclado K552", "keyboard", "input-keyboard-symbolic"), ("Macros", "macros", "media-record-symbolic"), ("Perfis", "profiles", "document-save-symbolic"))
KEY_ROWS = (
    (("Esc", 1), ("F1", 1), ("F2", 1), ("F3", 1), ("F4", 1), ("F5", 1), ("F6", 1), ("F7", 1), ("F8", 1), ("F9", 1), ("F10", 1), ("F11", 1), ("F12", 1), ("PrtSc", 1), ("ScrLk", 1), ("Pause", 1)),
    (("'", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1), ("=", 1), ("⌫", 2), ("Ins", 1), ("Home", 1), ("PgUp", 1)),
    (("Tab", 1.5), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1), ("´", 1), ("[", 1), ("Enter", 1.5), ("Del", 1), ("End", 1), ("PgDn", 1)),
    (("Caps", 1.75), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1), ("Ç", 1), ("~", 1), ("]", 1), ("Enter↵", 1.25)),
    (("Shift", 2.25), ("\\", 1), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), ("M", 1), (",", 1), (".", 1), (";", 1), ("Shift R", 2.25), ("↑", 1)),
    (("Ctrl", 1.25), ("Super", 1.25), ("Alt", 1.25), ("Espaço", 6.25), ("AltGr", 1.25), ("Fn", 1), ("Menu", 1), ("Ctrl R", 1.25), ("←", 1), ("↓", 1), ("→", 1)),
)

def label(text: str, css: str | None = None, xalign: float = 0) -> Gtk.Label:
    widget = Gtk.Label(label=text, xalign=xalign)
    if css:
        widget.add_css_class(css)
    return widget

def card() -> Gtk.Box:
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13)
    widget.add_css_class("control-card")
    return widget

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Redragon Control")
        self.set_default_size(1480, 1050)
        self.set_size_request(1080, 720)
        self._busy = self._loading = False
        self._mouse_dirty = self._keyboard_dirty = self._macros_dirty = False
        self._selected_keys: set[str] = set()
        self._key_buttons: dict[str, Gtk.Button] = {}
        self._dpi_rows: list[tuple[Gtk.Switch, Gtk.DropDown]] = []
        self._mapping_entries: dict[str, Gtk.Entry] = {}
        try:
            self.profiles, active = load_state(); self.profile_index = active - 1; self._mouse_loaded = True
        except (OSError, ValueError):
            self.profiles, self.profile_index, self._mouse_loaded = default_profiles(), 0, False
        try:
            self.keyboard_profiles, self.keyboard_profile_index = load_keyboard_profiles()
        except (OSError, ValueError):
            self.keyboard_profiles, self.keyboard_profile_index = default_keyboard_profiles(), 0
        try:
            self.macros = load_macros()
        except (OSError, ValueError):
            self.macros = default_macros()
        self.macro_index = 0

        self.toast_overlay = Adw.ToastOverlay(); self.set_content(self.toast_overlay)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.toast_overlay.set_child(root)
        header = Adw.HeaderBar(); root.append(header)
        title = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title.append(label("Redragon Control", "heading", .5)); title.append(label("S118 · M711 Cobra + K552 Kumara", "dim-label", .5)); header.set_title_widget(title)
        self.mouse_chip = self._status_chip("M711", "input-mouse-symbolic"); self.keyboard_chip = self._status_chip("K552", "input-keyboard-symbolic")
        header.pack_start(self.mouse_chip); header.pack_start(self.keyboard_chip)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Atualizar dispositivos"); refresh.add_css_class("flat"); refresh.connect("clicked", lambda *_: self._refresh_status()); header.pack_end(refresh)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True); root.append(body); body.append(self._build_sidebar())
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True, vexpand=True)
        self.stack.add_named(self._overview_page(), "overview"); self.stack.add_named(self._mouse_page(), "mouse"); self.stack.add_named(self._keyboard_page(), "keyboard"); self.stack.add_named(self._macros_page(), "macros"); self.stack.add_named(self._profiles_page(), "profiles"); body.append(self.stack)
        self._load_mouse(self.profile_index); self._load_keyboard(self.keyboard_profile_index); self._load_macro(0); self._select_navigation("keyboard"); self._refresh_status(); GLib.idle_add(self._scroll_keyboard_top)
        if not self._mouse_loaded and os.environ.get("REDRAGON_PREVIEW") != "1": GLib.idle_add(self._read_silently)

    def _status_chip(self, text, icon):
        box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER); box.add_css_class("status-chip"); box.append(Gtk.Image.new_from_icon_name(icon)); box.append(label(text)); dot = Gtk.Image.new_from_icon_name("media-record-symbolic"); dot.set_pixel_size(8); box.append(dot); box.status_dot = dot; return box

    def _build_sidebar(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16); side.add_css_class("sidebar"); side.set_size_request(236, -1)
        self.navigation = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE); self.navigation.add_css_class("navigation-sidebar"); self.navigation.connect("row-selected", self._on_navigation)
        for title, page, icon in NAVIGATION:
            row = Gtk.ListBoxRow(); row.page_name = page; content = Gtk.Box(spacing=12); content.append(Gtk.Image.new_from_icon_name(icon)); content.append(label(title)); row.set_child(content); self.navigation.append(row)
        side.append(self.navigation); side.append(Gtk.Box(vexpand=True))
        side.append(label("PERFIL DO TECLADO", "section-kicker")); self.global_profile = Gtk.DropDown.new_from_strings([p.name for p in self.keyboard_profiles]); self.global_profile.set_selected(self.keyboard_profile_index); self.global_profile.connect("notify::selected", self._on_keyboard_profile_changed); side.append(self.global_profile)
        self.apply_button = Gtk.Button(label="Aplicar configurações"); self.apply_button.add_css_class("suggested-action"); self.apply_button.add_css_class("apply-button"); self.apply_button.connect("clicked", self._on_apply_all); side.append(self.apply_button)
        self.save_button = Gtk.Button(label="Salvar perfil"); self.save_button.connect("clicked", self._on_save_local); side.append(self.save_button); return side

    def _shell(self, title, subtitle):
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18); content.add_css_class("page-content"); heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); heading.append(label(title, "title-1")); heading.append(label(subtitle, "dim-label")); content.append(heading); scroll.set_child(content); return scroll, content

    def _overview_page(self):
        scroll, content = self._shell("Visão geral", "Seu kit Redragon S118 em um só lugar")
        devices = Gtk.Box(spacing=16, homogeneous=True)
        for title, sub, icon, detail in (("M711 Cobra", "Mouse gamer", "input-mouse-symbolic", "Até 10.000 DPI · 1000 Hz"), ("K552 Kumara", "Teclado mecânico ABNT2", "input-keyboard-symbolic", "RGB por tecla · TKL")):
            c = card(); image = Gtk.Image.new_from_icon_name(icon); image.set_pixel_size(48); image.set_halign(Gtk.Align.START); image.add_css_class("device-icon"); c.append(image); c.append(label(title, "title-2")); c.append(label(sub, "dim-label")); c.append(label(detail, "caption")); devices.append(c)
        content.append(devices); note = card(); note.append(label("Configurações armazenadas", "title-3")); t = label("Os perfis do mouse são gravados na memória interna. O teclado salva o efeito no firmware e mantém uma cópia local para restaurar a sessão.", "dim-label"); t.set_wrap(True); note.append(t); content.append(note); return scroll

    def _field(self, title, control):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); box.add_css_class("field"); box.append(label(title, "caption")); box.append(control); return box

    def _dropdown(self, parent, title, values, callback):
        widget = Gtk.DropDown.new_from_strings(values); widget.connect("notify::selected", callback); parent.append(self._field(title, widget)); return widget

    def _mouse_page(self):
        scroll, content = self._shell("Mouse M711 Cobra", "Sensibilidade, desempenho, iluminação e dez controles programáveis")
        top = Gtk.Box(spacing=12); top.append(label("Perfil interno", "title-3")); self.mouse_profile_dropdown = Gtk.DropDown.new_from_strings([f"Perfil {i}" for i in range(1, 6)]); self.mouse_profile_dropdown.set_selected(self.profile_index); self.mouse_profile_dropdown.connect("notify::selected", self._on_mouse_profile_changed); top.append(self.mouse_profile_dropdown); read = Gtk.Button(label="Ler do mouse", icon_name="view-refresh-symbolic"); read.connect("clicked", self._on_read_mouse); top.append(read); content.append(top)
        columns = Gtk.Box(spacing=16, homogeneous=True); dpi = card(); dpi.append(label("Níveis de DPI", "title-3")); dpi.append(label("Cinco estágios alternados pelos botões DPI", "dim-label"))
        for level in range(5):
            row = Gtk.Box(spacing=10); enabled = Gtk.Switch(valign=Gtk.Align.CENTER); dropdown = Gtk.DropDown(model=Gtk.StringList.new([str(v) for v in DPI_VALUES]), hexpand=True); enabled.connect("notify::active", self._mouse_changed); dropdown.connect("notify::selected", self._mouse_changed); row.append(enabled); row.append(label(f"Nível {level+1}")); row.append(dropdown); dpi.append(row); self._dpi_rows.append((enabled, dropdown))
        columns.append(dpi); perf = card(); perf.append(label("Desempenho e RGB", "title-3")); self.rate_dropdown = self._dropdown(perf, "Polling rate", [f"{v} Hz" for v in REPORT_RATES], self._mouse_changed); self.mouse_light_dropdown = self._dropdown(perf, "Efeito", [LIGHT_LABELS[v] for v in LIGHT_MODES], self._mouse_changed); self.mouse_color = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Cor do mouse")); self.mouse_color.connect("notify::rgba", self._mouse_changed); perf.append(self._field("Cor", self.mouse_color)); self.mouse_brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 3, 1); self.mouse_brightness.connect("value-changed", self._mouse_changed); perf.append(self._field("Brilho", self.mouse_brightness)); self.mouse_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 8, 1); self.mouse_speed.set_tooltip_text("1 = lenta · 8 = rápida"); self.mouse_speed.connect("value-changed", self._mouse_changed); perf.append(self._field("Velocidade", self.mouse_speed)); columns.append(perf); content.append(columns)
        mapping = card(); mapping.append(label("Mapeamento dos botões", "title-3")); mapping.append(label("Use botões, teclas, atalhos, macro1…macro15, fire ou snipe.", "dim-label")); grid = Gtk.Grid(column_spacing=18, row_spacing=10, column_homogeneous=True)
        for index, name in enumerate(BUTTON_NAMES):
            entry = Gtk.Entry(placeholder_text="Função"); entry.connect("changed", self._mouse_changed); grid.attach(self._field(BUTTON_LABELS[name], entry), index % 2, index // 2, 1, 1); self._mapping_entries[name] = entry
        mapping.append(grid); content.append(mapping); return scroll

    def _keyboard_page(self):
        scroll, content = self._shell("Teclado K552 Kumara", "Iluminação RGB completa, personalização por tecla e atalhos")
        self.keyboard_page_scroll = scroll
        editor = card(); editor.add_css_class("keyboard-editor"); head = Gtk.Box(spacing=8); head.append(label("Editor por tecla", "title-3")); self.selected_keys_label = label("Nenhuma tecla selecionada", "dim-label", 1); self.selected_keys_label.set_hexpand(True); head.append(self.selected_keys_label); all_button = Gtk.Button(label="Todas"); all_button.add_css_class("flat"); all_button.connect("clicked", lambda *_: self._select_all()); clear = Gtk.Button(label="Limpar"); clear.add_css_class("flat"); clear.connect("clicked", lambda *_: self._clear_selection()); head.append(all_button); head.append(clear); editor.append(head)
        kscroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=322); keyboard = Gtk.Grid(column_spacing=4, row_spacing=6, column_homogeneous=True, row_homogeneous=True, hexpand=True); keyboard.add_css_class("keyboard-canvas")
        key_counter = 0
        for row_index, row_data in enumerate(KEY_ROWS):
            column = 0
            for key, width in row_data:
                span = round(width * 4); button = Gtk.Button(label=key); button.add_css_class("keyboard-key"); button.add_css_class(f"key-tone-{min(7, key_counter * 8 // max(1, len(row_data)))}"); button.set_size_request(-1, 42); button.connect("clicked", self._on_key_clicked, key); keyboard.attach(button, column, row_index, span, 1); self._key_buttons[key] = button; key_counter += 1; column += span
            key_counter = 0
        kscroll.set_child(keyboard); editor.append(kscroll); content.append(editor)

        settings = card(); settings.add_css_class("compact-settings"); settings.append(label("Iluminação e comportamento", "title-3")); columns = Gtk.Grid(column_spacing=22, row_spacing=8, column_homogeneous=True)
        light = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); light.append(label("EFEITO E COR", "section-kicker")); self.keyboard_mode = self._dropdown(light, "Efeito", [KEYBOARD_MODE_LABELS[v] for v in KEYBOARD_MODES], self._keyboard_changed); self.keyboard_color = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Cor das teclas")); self.keyboard_color.connect("notify::rgba", self._on_keyboard_color); light.append(self._field("Cor", self.keyboard_color)); columns.attach(light, 0, 0, 1, 1)
        levels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); levels.append(label("INTENSIDADE", "section-kicker")); self.keyboard_brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 25); self.keyboard_brightness.set_draw_value(True); self.keyboard_brightness.connect("value-changed", self._keyboard_changed); levels.append(self._field("Brilho", self.keyboard_brightness)); self.keyboard_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 20); self.keyboard_speed.set_draw_value(True); self.keyboard_speed.connect("value-changed", self._keyboard_changed); levels.append(self._field("Velocidade", self.keyboard_speed)); columns.attach(levels, 1, 0, 1, 1)
        behavior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); behavior.append(label("AÇÃO", "section-kicker")); self._direction_values = ("right", "left", "up", "down"); self.direction = self._dropdown(behavior, "Direção", ["Direita", "Esquerda", "Cima", "Baixo"], self._keyboard_changed); self.key_action = Gtk.Entry(placeholder_text="Ex.: macro1, media_play ou ctrl_l+c"); behavior.append(self._field("Ação das teclas", self.key_action)); assign = Gtk.Button(label="Atribuir à seleção"); assign.connect("clicked", self._assign_key_action); behavior.append(assign); columns.attach(behavior, 2, 0, 1, 1)
        settings.append(columns); content.append(settings); return scroll

    def _scroll_keyboard_top(self):
        self.keyboard_page_scroll.get_vadjustment().set_value(0)
        return GLib.SOURCE_REMOVE

    def _macros_page(self):
        scroll, content = self._shell("Macros do mouse", "Edite os 15 slots gravados na memória interna do M711"); area = Gtk.Box(spacing=16); slots = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE); slots.set_size_request(210, 420); slots.add_css_class("boxed-list"); slots.connect("row-selected", self._on_macro_selected)
        for i in range(15): row = Gtk.ListBoxRow(); row.macro_index = i; row.set_child(label(f"Macro {i+1}")); slots.append(row)
        self.macro_slots = slots; area.append(slots); editor = card(); editor.set_hexpand(True); self.macro_name = Gtk.Entry(placeholder_text="Nome da macro"); self.macro_name.connect("changed", self._macro_changed); editor.append(self._field("Nome", self.macro_name)); editor.append(label("Ações", "title-3")); editor.append(label("Uma por linha: down\tkey, up\tkey, delay\t10, move_left\t20…", "dim-label")); self.macro_buffer = Gtk.TextBuffer(); self.macro_buffer.connect("changed", self._macro_changed); view = Gtk.TextView(buffer=self.macro_buffer, monospace=True, vexpand=True); editor.append(view); area.append(editor); content.append(area); GLib.idle_add(lambda: (slots.select_row(slots.get_row_at_index(0)), False)[1]); return scroll

    def _profiles_page(self):
        scroll, content = self._shell("Perfis", "Organize, salve e restaure configurações do kit")
        for i, profile in enumerate(self.keyboard_profiles):
            row = card(); head = Gtk.Box(spacing=10); head.append(label(profile.name, "title-3")); sub = label(f"K552 · {KEYBOARD_MODE_LABELS[profile.mode]}", "dim-label"); sub.set_hexpand(True); head.append(sub); button = Gtk.Button(label="Ativar"); button.connect("clicked", self._activate_profile, i); head.append(button); row.append(head); content.append(row)
        note = card(); note.append(label("Backup local automático", "title-3")); note.append(label("As configurações ficam em ~/.config/redragon-control e sobrevivem ao fechamento do aplicativo.", "dim-label")); content.append(note); return scroll

    def _on_navigation(self, _box, row):
        if row is not None and hasattr(self, "stack"): self.stack.set_visible_child_name(row.page_name)
    def _select_navigation(self, page):
        for i, (_, name, _) in enumerate(NAVIGATION):
            if name == page: self.navigation.select_row(self.navigation.get_row_at_index(i)); return
    def _refresh_status(self):
        m, k = device_status(), keyboard_status(); self._mouse_ready = m.connected and m.accessible and bool(m.backend_path); self._keyboard_ready = k.connected and k.accessible
        for chip, ready in ((self.mouse_chip, self._mouse_ready), (self.keyboard_chip, self._keyboard_ready)):
            chip.status_dot.remove_css_class("status-ok"); chip.status_dot.remove_css_class("status-error"); chip.status_dot.add_css_class("status-ok" if ready else "status-error")
        self._update_buttons()

    def _load_mouse(self, index):
        self._loading = True; self.profile_index = index; p = self.profiles[index]
        for i, (switch, dropdown) in enumerate(self._dpi_rows): switch.set_active(p.dpi_enabled[i]); dropdown.set_selected(DPI_VALUES.index(p.dpi[i]))
        self.rate_dropdown.set_selected(REPORT_RATES.index(p.report_rate)); self.mouse_light_dropdown.set_selected(LIGHT_MODES.index(p.light_mode)); rgba = Gdk.RGBA(); rgba.parse(f"#{p.color}"); self.mouse_color.set_rgba(rgba); self.mouse_brightness.set_value(p.brightness); self.mouse_speed.set_value(mouse_speed_to_ui(p.speed))
        for name, entry in self._mapping_entries.items(): entry.set_text(p.button_mappings[name])
        self._loading = False
    def _store_mouse(self):
        p = self.profiles[self.profile_index]; p.dpi_enabled = [s.get_active() for s, _ in self._dpi_rows]; p.dpi = [DPI_VALUES[d.get_selected()] for _, d in self._dpi_rows]; p.report_rate = REPORT_RATES[self.rate_dropdown.get_selected()]; p.light_mode = LIGHT_MODES[self.mouse_light_dropdown.get_selected()]; p.color = self._hex(self.mouse_color.get_rgba()); p.brightness = round(self.mouse_brightness.get_value()); p.speed = mouse_speed_from_ui(round(self.mouse_speed.get_value()))
        for name, entry in self._mapping_entries.items(): p.button_mappings[name] = entry.get_text().strip()
    def _mouse_changed(self, *_):
        if not self._loading: self._store_mouse(); self._mouse_dirty = True; self._update_buttons()
    def _on_mouse_profile_changed(self, dropdown, _):
        if not self._loading: self._store_mouse(); self._load_mouse(dropdown.get_selected()); self._mouse_dirty = True; self._update_buttons()

    def _load_keyboard(self, index):
        self._loading = True; self.keyboard_profile_index = index; p = self.keyboard_profiles[index]; self.keyboard_mode.set_selected(KEYBOARD_MODES.index(p.mode)); rgba = Gdk.RGBA(); rgba.parse(f"#{p.color}"); self.keyboard_color.set_rgba(rgba); self.keyboard_brightness.set_value(normalize_keyboard_brightness(p.brightness)); self.keyboard_speed.set_value(normalize_keyboard_speed(p.speed)); self._update_keyboard_control_state(p.direction); self._paint_keyboard(); self._loading = False
    def _store_keyboard(self):
        p = self.keyboard_profiles[self.keyboard_profile_index]; p.mode = KEYBOARD_MODES[self.keyboard_mode.get_selected()]; p.color = self._hex(self.keyboard_color.get_rgba()); p.brightness = normalize_keyboard_brightness(round(self.keyboard_brightness.get_value())); p.speed = normalize_keyboard_speed(round(self.keyboard_speed.get_value())); p.direction = self._direction_values[self.direction.get_selected()]
    def _update_keyboard_control_state(self, preferred_direction=None):
        mode = KEYBOARD_MODES[self.keyboard_mode.get_selected()]
        self.keyboard_speed.set_sensitive(mode in KEYBOARD_SPEED_MODES)
        allowed = KEYBOARD_DIRECTION_MODES.get(mode)
        self.direction.set_sensitive(allowed is not None)
        values = allowed or ("right", "left", "up", "down")
        labels = {"right": "Direita", "left": "Esquerda", "up": "Cima", "down": "Baixo"}
        current = preferred_direction or self._direction_values[self.direction.get_selected()]
        self._direction_values = values
        self.direction.set_model(Gtk.StringList.new([labels[value] for value in values]))
        self.direction.set_selected(values.index(current) if current in values else 0)
    def _keyboard_changed(self, widget=None, *_):
        if not self._loading:
            if widget is self.keyboard_mode:
                self._loading = True; self._update_keyboard_control_state(self.keyboard_profiles[self.keyboard_profile_index].direction); self._loading = False
            self._store_keyboard(); self._keyboard_dirty = True; self._paint_keyboard(); self._update_buttons()
    def _on_keyboard_color(self, *_):
        if self._loading: return
        color = self._hex(self.keyboard_color.get_rgba()); p = self.keyboard_profiles[self.keyboard_profile_index]
        if self._selected_keys:
            for key in self._selected_keys: p.key_colors[key] = color
        else: p.color = color
        self._keyboard_changed()
    def _on_keyboard_profile_changed(self, dropdown, _):
        if not self._loading: self._store_keyboard(); self._load_keyboard(dropdown.get_selected()); self._keyboard_dirty = True; self._update_buttons()
    def _on_key_clicked(self, button, key):
        if key in self._selected_keys: self._selected_keys.remove(key); button.remove_css_class("selected-key")
        else: self._selected_keys.add(key); button.add_css_class("selected-key")
        self._selection_label()
    def _select_all(self):
        self._selected_keys = set(self._key_buttons)
        for b in self._key_buttons.values(): b.add_css_class("selected-key")
        self._selection_label()
    def _clear_selection(self):
        self._selected_keys.clear()
        for b in self._key_buttons.values(): b.remove_css_class("selected-key")
        self._selection_label()
    def _selection_label(self):
        n = len(self._selected_keys); self.selected_keys_label.set_text("Nenhuma tecla selecionada" if not n else f"{n} tecla{'s' if n != 1 else ''} selecionada{'s' if n != 1 else ''}")
    def _paint_keyboard(self):
        p = self.keyboard_profiles[self.keyboard_profile_index]
        for key, button in self._key_buttons.items(): button.set_tooltip_text(f"{key} · #{p.key_colors.get(key, p.color).upper()}")
    def _assign_key_action(self, _):
        action = self.key_action.get_text().strip()
        if not self._selected_keys or not action: self._toast("Selecione ao menos uma tecla e informe a ação."); return
        for key in self._selected_keys: self.keyboard_profiles[self.keyboard_profile_index].key_actions[key] = action
        self._keyboard_dirty = True; self._update_buttons(); self._toast(f"Ação atribuída a {len(self._selected_keys)} tecla(s).")

    def _load_macro(self, index):
        self._loading = True; self.macro_index = index; m = self.macros[index]; self.macro_name.set_text(m.name); self.macro_buffer.set_text("\n".join(m.actions)); self._loading = False
    def _store_macro(self):
        m = self.macros[self.macro_index]; m.name = self.macro_name.get_text().strip() or f"Macro {self.macro_index+1}"; m.actions = self.macro_buffer.get_text(self.macro_buffer.get_start_iter(), self.macro_buffer.get_end_iter(), False).splitlines()
    def _macro_changed(self, *_):
        if not self._loading: self._store_macro(); self._macros_dirty = True; self._update_buttons()
    def _on_macro_selected(self, _, row):
        if row is not None and hasattr(self, "macro_name"):
            if not self._loading: self._store_macro()
            self._load_macro(row.macro_index)
    def _activate_profile(self, _, index): self.global_profile.set_selected(index); self._select_navigation("keyboard")

    def _on_read_mouse(self, _): self._background(self._read_mouse, "Configurações lidas do mouse.")
    def _read_silently(self):
        if self._mouse_ready: self._background(self._read_mouse, None)
        return GLib.SOURCE_REMOVE
    def _read_mouse(self):
        profiles, active = read_configuration()
        def update():
            self.profiles = profiles; self._mouse_loaded = True; self._loading = True; self.mouse_profile_dropdown.set_selected(active-1); self._loading = False; self._load_mouse(active-1); self._mouse_dirty = False; save_state(self.profiles, active); return False
        GLib.idle_add(update)
    def _on_save_local(self, _):
        try: self._store_mouse(); self._store_keyboard(); self._store_macro(); save_state(self.profiles, self.profile_index+1); save_keyboard_profiles(self.keyboard_profiles, self.keyboard_profile_index); save_macros(self.macros); self._toast("Perfil salvo neste computador.")
        except (OSError, ValueError) as error: self._toast(str(error))
    def _on_apply_all(self, _):
        self._store_mouse(); self._store_keyboard(); self._store_macro()
        try:
            plan = build_apply_plan(
                mouse_dirty=self._mouse_dirty,
                keyboard_dirty=self._keyboard_dirty,
                macros_dirty=self._macros_dirty,
                mouse_dpi_enabled=self.profiles[self.profile_index].dpi_enabled,
            )
        except ValueError as error:
            self._toast(str(error)); return
        mice, keyboards, macros = deepcopy(self.profiles), deepcopy(self.keyboard_profiles), deepcopy(self.macros); mi, ki = self.profile_index+1, self.keyboard_profile_index
        applied = {"mouse": False, "keyboard": False}

        # Retire apenas as alterações incluídas neste snapshot. Se o usuário
        # editar algo enquanto o backend trabalha, os callbacks tornam o estado
        # dirty novamente e a nova alteração não é perdida.
        if plan.mouse_settings: self._mouse_dirty = False
        if plan.macros: self._macros_dirty = False
        if plan.keyboard: self._keyboard_dirty = False

        def operation():
            errors = []
            if plan.mouse:
                save_state(mice, mi); save_macros(macros)
                if self._mouse_ready:
                    try: apply_profiles(mice, mi, serialize_macros(macros)); applied["mouse"] = True
                    except Exception as e: errors.append(f"Mouse: {e}")
                else: errors.append("Mouse: dispositivo ou permissão indisponível")
            if plan.keyboard:
                save_keyboard_profiles(keyboards, ki)
                if self._keyboard_ready:
                    try: apply_keyboard(keyboards[ki]); applied["keyboard"] = True
                    except Exception as e: errors.append(f"Teclado: {e}")
                else: errors.append("Teclado: dispositivo ou permissão HID indisponível")
            if errors: raise KeyboardError("\n".join(errors))

        def complete(_error):
            if plan.mouse and not applied["mouse"]:
                if plan.mouse_settings: self._mouse_dirty = True
                if plan.macros: self._macros_dirty = True
            if plan.keyboard and not applied["keyboard"]:
                self._keyboard_dirty = True
            self._update_buttons()

        self._background(operation, "Configurações aplicadas e salvas.", complete=complete)
    def _background(self, operation, message, after=None, complete=None):
        self._busy = True; self._update_buttons()
        def worker():
            try: operation(); GLib.idle_add(done, None)
            except Exception as error: GLib.idle_add(done, error)
        def done(error):
            self._busy = False
            if complete: complete(error)
            self._update_buttons()
            if error: self._toast(str(error) if isinstance(error, (BackendError, KeyboardError, ValueError, OSError)) else "Falha inesperada ao configurar os dispositivos.")
            else:
                if after: after()
                if message: self._toast(message)
            self._refresh_status(); return False
        threading.Thread(target=worker, daemon=True).start()
    def _update_buttons(self):
        if hasattr(self, "apply_button"): self.apply_button.set_sensitive((self._mouse_dirty or self._keyboard_dirty or self._macros_dirty) and not self._busy); self.save_button.set_sensitive(not self._busy)
    def _toast(self, message): self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
    @staticmethod
    def _hex(rgba): return "{:02x}{:02x}{:02x}".format(round(rgba.red*255), round(rgba.green*255), round(rgba.blue*255))

class RedragonApplication(Adw.Application):
    def __init__(self): super().__init__(application_id="io.github.redragon.Control")
    def do_startup(self):
        Adw.Application.do_startup(self); provider = Gtk.CssProvider(); provider.load_from_string("""
        window { background: #17171b; } .sidebar { background: #202024; padding: 18px 14px; border-right: 1px solid alpha(white, .07); }
        .navigation-sidebar row { padding: 12px 14px; margin: 2px 0; border-radius: 10px; } .navigation-sidebar row:selected { background: alpha(#9b5cff, .22); color: #d8c4ff; }
        .page-content { padding: 26px 30px 38px; } .control-card { background: #25252a; border: 1px solid alpha(white, .07); border-radius: 15px; padding: 18px; }
        .keyboard-editor { padding: 18px 20px 20px; } .keyboard-canvas { background: #19191d; border-radius: 12px; padding: 16px; }
        .keyboard-key { min-width: 34px; min-height: 38px; padding: 2px 5px; font-size: 11px; background: #32323a; border: 1px solid alpha(white, .10); border-radius: 6px; color: #f4f0ff; box-shadow: inset 0 -2px alpha(black, .35); }
        .keyboard-key:hover { background: #3e3a4b; } .keyboard-key.selected-key { background: #7446ba; border-color: #b695ee; box-shadow: 0 0 8px alpha(#9b5cff, .6); }
        .keyboard-key.key-tone-0 { background: #61383d; border-color: #8a4b53; } .keyboard-key.key-tone-1 { background: #60432c; border-color: #8d633a; }
        .keyboard-key.key-tone-2 { background: #53512d; border-color: #77763a; } .keyboard-key.key-tone-3 { background: #31513a; border-color: #447854; }
        .keyboard-key.key-tone-4 { background: #295053; border-color: #37767c; } .keyboard-key.key-tone-5 { background: #2d465f; border-color: #3e668c; }
        .keyboard-key.key-tone-6 { background: #413b68; border-color: #5f5793; } .keyboard-key.key-tone-7 { background: #603b60; border-color: #8a538a; }
        .status-chip { background: alpha(white, .055); border-radius: 99px; padding: 5px 10px; } .status-dot.status-ok { color: #45d483; } .status-dot.status-error { color: #ee6b73; }
        .section-kicker { font-size: 10px; font-weight: 700; letter-spacing: 1px; color: alpha(white, .55); } .caption { font-size: 12px; color: alpha(white, .68); } .device-icon { color: #a976f0; } .apply-button { min-height: 40px; } .field { margin: 1px 0 4px; }
        """); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    def do_activate(self): (self.props.active_window or MainWindow(application=self)).present()

def main() -> int: return RedragonApplication().run(None)
if __name__ == "__main__": raise SystemExit(main())
