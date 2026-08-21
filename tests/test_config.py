import unittest

from redragon_control.config import (
    Profile,
    default_profiles,
    parse,
    parse_active_profile,
    serialize,
    validate_profiles,
)


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        profiles = default_profiles()
        profiles[2] = Profile(
            dpi=[100, 800, 1600, 3200, 10000],
            dpi_enabled=[False, True, True, True, False],
            report_rate=500,
            light_mode="wave",
            color="12abef",
            brightness=2,
            speed=7,
        )
        self.assertEqual(parse(serialize(profiles)), profiles)

    def test_rejects_all_dpi_levels_disabled(self):
        profiles = default_profiles()
        profiles[0].dpi_enabled = [False] * 5
        with self.assertRaisesRegex(ValueError, "ao menos um nível"):
            validate_profiles(profiles)

    def test_serialized_config_has_all_profiles(self):
        text = serialize(default_profiles())
        self.assertEqual(text.count("[profile"), 5)
        self.assertIn("button_forward=forward", text)
        self.assertIn("scrollspeed=1", text)

    def test_active_profile_round_trip(self):
        text = serialize(default_profiles(), active_profile=4)
        self.assertEqual(parse_active_profile(text), 4)
        self.assertIn("report_rate=1000", text)

    def test_parses_backend_xy_dpi_format(self):
        text = serialize(default_profiles()).replace("dpi1=500", "dpi1=X800Y800", 1)
        self.assertEqual(parse(text)[0].dpi[0], 800)

    def test_parses_m711_raw_dpi_and_ignores_invalid_speed(self):
        text = serialize(default_profiles()).replace("dpi1=500", "dpi1=0x68000000", 1)
        text = text.replace("speed=4", "speed=0", 1)
        profile = parse(text)[0]
        self.assertEqual(profile.dpi[0], 4500)
        self.assertEqual(profile.speed, 4)

    def test_rejects_different_xy_axes_without_overwriting_them(self):
        text = serialize(default_profiles()).replace("dpi1=500", "dpi1=X800Y900", 1)
        with self.assertRaisesRegex(ValueError, "eixos separadamente"):
            parse(text)


if __name__ == "__main__":
    unittest.main()
