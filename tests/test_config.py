import os
import unittest
from unittest.mock import patch

from mir_multiagent.config import ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_mock_defaults_are_executable_without_secret(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.provider, "mock")

    def test_groq_requires_key(self) -> None:
        with patch.dict(
            os.environ,
            {"MIR_LLM_PROVIDER": "groq", "MIR_LLM_MODEL": "test-model"},
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigurationError, "GROQ_API_KEY"):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
