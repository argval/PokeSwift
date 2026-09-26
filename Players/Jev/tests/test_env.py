import os
import tempfile
import unittest
from pathlib import Path

from jev_player.env import load_player_env


class EnvTests(unittest.TestCase):
    def test_missing_env_file_is_a_no_op(self):
        missing = Path(tempfile.mkdtemp()) / "missing.env"
        self.assertIsNone(load_player_env(missing))

    def test_loads_env_without_overwriting_existing_exports(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as handle:
            handle.write("TYPESAFE_API_KEY=from-file\nJEV_ENV_TEST_VALUE=loaded\n")
            env_path = handle.name
        previous_key = os.environ.get("TYPESAFE_API_KEY")
        previous_test = os.environ.pop("JEV_ENV_TEST_VALUE", None)
        os.environ["TYPESAFE_API_KEY"] = "from-shell"
        try:
            loaded = load_player_env(env_path)
            self.assertEqual(loaded, Path(env_path))
            self.assertEqual(os.environ["TYPESAFE_API_KEY"], "from-shell")
            self.assertEqual(os.environ["JEV_ENV_TEST_VALUE"], "loaded")
        finally:
            if previous_key is None:
                os.environ.pop("TYPESAFE_API_KEY", None)
            else:
                os.environ["TYPESAFE_API_KEY"] = previous_key
            if previous_test is None:
                os.environ.pop("JEV_ENV_TEST_VALUE", None)
            else:
                os.environ["JEV_ENV_TEST_VALUE"] = previous_test
            Path(env_path).unlink(missing_ok=True)
