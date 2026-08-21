import unittest

from redragon_control.apply_plan import build_apply_plan


class ApplyPlanTests(unittest.TestCase):
    def test_keyboard_only_does_not_validate_or_apply_mouse(self):
        plan = build_apply_plan(
            mouse_dirty=False,
            keyboard_dirty=True,
            macros_dirty=False,
            mouse_dpi_enabled=[False] * 5,
        )
        self.assertFalse(plan.mouse)
        self.assertTrue(plan.keyboard)

    def test_macro_change_is_applied_to_mouse(self):
        plan = build_apply_plan(
            mouse_dirty=False,
            keyboard_dirty=False,
            macros_dirty=True,
            mouse_dpi_enabled=[True, False, False, False, False],
        )
        self.assertTrue(plan.mouse)
        self.assertTrue(plan.macros)

    def test_mouse_change_still_requires_an_enabled_dpi(self):
        with self.assertRaisesRegex(ValueError, "ao menos um nível"):
            build_apply_plan(
                mouse_dirty=True,
                keyboard_dirty=False,
                macros_dirty=False,
                mouse_dpi_enabled=[False] * 5,
            )


if __name__ == "__main__":
    unittest.main()
