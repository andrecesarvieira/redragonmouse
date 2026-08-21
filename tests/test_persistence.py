import tempfile
import unittest
from pathlib import Path

from redragon_control.config import default_profiles
from redragon_control.persistence import load_state, save_state


class PersistenceTests(unittest.TestCase):
    def test_saves_profiles_and_active_profile(self):
        profiles = default_profiles()
        profiles[2].dpi[0] = 4500
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.ini"
            save_state(profiles, 3, path)
            loaded, active = load_state(path)
        self.assertEqual(loaded, profiles)
        self.assertEqual(active, 3)


if __name__ == "__main__":
    unittest.main()
