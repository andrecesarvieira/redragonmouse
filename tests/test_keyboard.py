import tempfile
import unittest
from pathlib import Path

from redragon_control.keyboard import (
    COLOR_DATA_SIZE,
    K552_LED_INDEX,
    K552_KEY_ORDER,
    _packets_for_profile,
    default_keyboard_profiles,
    load_keyboard_profiles,
    normalize_keyboard_brightness,
    normalize_keyboard_speed,
    save_keyboard_profiles,
)
from redragon_control.macros import Macro, load_macros, save_macros, serialize_macros


class KeyboardPersistenceTests(unittest.TestCase):
    def test_keyboard_profiles_round_trip(self):
        profiles = default_keyboard_profiles()
        profiles[0].key_colors["W"] = "ff0000"
        profiles[0].key_actions["F1"] = "macro1"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keyboard.json"
            save_keyboard_profiles(profiles, 1, path)
            loaded, active = load_keyboard_profiles(path)
        self.assertEqual(loaded, profiles)
        self.assertEqual(active, 1)

    def test_macros_round_trip_and_backend_format(self):
        macros = [Macro("Copiar", ["down\tctrl_l", "down\tc", "up\tc", "up\tctrl_l"])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macros.json"
            save_macros(macros, path)
            loaded = load_macros(path)
        self.assertEqual(loaded[0], macros[0])
        text = serialize_macros(loaded)
        self.assertIn(";## macro1", text)
        self.assertIn(";# down\tctrl_l", text)

    def test_custom_mode_sends_per_key_colors(self):
        profile = default_keyboard_profiles()[0]
        profile.key_colors["W"] = "ff0000"
        packets = _packets_for_profile(profile)
        self.assertEqual(len(packets), 8)
        color_data = b"".join(packet[8:8 + packet[4]] for packet in packets[1:])
        self.assertEqual(len(color_data), COLOR_DATA_SIZE)
        start = K552_LED_INDEX["W"] * 3
        self.assertEqual(color_data[start:start + 3], bytes.fromhex("ff0000"))

    def test_all_visual_keys_have_unique_led_positions(self):
        self.assertEqual(set(K552_KEY_ORDER), set(K552_LED_INDEX))
        self.assertEqual(len(set(K552_LED_INDEX.values())), len(K552_KEY_ORDER))
        self.assertLess(max(K552_LED_INDEX.values()), 126)

    def test_packets_have_report_id_checksum_and_fixed_size(self):
        for packet in _packets_for_profile(default_keyboard_profiles()[0]):
            self.assertEqual(len(packet), 64)
            self.assertEqual(packet[0], 0x04)
            checksum = sum(packet[3:]) & 0xFFFF
            self.assertEqual(packet[1] | packet[2] << 8, checksum)

    def test_mode_scaling_uses_native_evision_ranges(self):
        profile = default_keyboard_profiles()[1]
        profile.brightness = 85
        profile.speed = 70
        profile.direction = "right"
        parameters = _packets_for_profile(profile)[0][8:16]
        self.assertEqual(parameters[:5], bytes((0x08, 3, 1, 1, 0)))

    def test_mode_scaling_has_balanced_discrete_levels_and_correct_endpoints(self):
        self.assertEqual([normalize_keyboard_brightness(value) for value in (0, 25, 50, 75, 100)], [0, 25, 50, 75, 100])
        self.assertEqual([normalize_keyboard_speed(value) for value in (0, 20, 40, 60, 80, 100)], [0, 20, 40, 60, 80, 100])

        profile = default_keyboard_profiles()[1]
        profile.brightness = 0
        profile.speed = 0
        self.assertEqual(_packets_for_profile(profile)[0][9:11], bytes((0, 5)))
        profile.brightness = 100
        profile.speed = 100
        self.assertEqual(_packets_for_profile(profile)[0][9:11], bytes((4, 0)))


if __name__ == "__main__":
    unittest.main()
