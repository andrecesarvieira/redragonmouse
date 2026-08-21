import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from redragon_control.keyboard import apply_keyboard, default_keyboard_profiles, load_keyboard_profiles, save_keyboard_profiles
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

    @patch("redragon_control.keyboard._run_openrgb")
    @patch("redragon_control.keyboard._device_index", return_value=2)
    def test_custom_mode_sends_per_key_colors(self, _index, run):
        profile = default_keyboard_profiles()[0]
        profile.key_colors["W"] = "ff0000"
        apply_keyboard(profile)
        arguments = run.call_args.args
        colors = arguments[arguments.index("--color") + 1]
        self.assertIn("FF0000", colors.split(","))
        self.assertGreater(len(colors.split(",")), 80)


if __name__ == "__main__":
    unittest.main()
