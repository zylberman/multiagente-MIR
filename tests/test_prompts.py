import unittest
from importlib import resources

from mir_multiagent.prompts import REQUIRED_PROMPTS, load_prompts


class PackagedPromptTests(unittest.TestCase):
    def test_prompts_are_package_resources(self) -> None:
        resource = resources.files("mir_multiagent.resources").joinpath("prompts.json")
        self.assertTrue(resource.is_file())
        self.assertEqual(set(load_prompts()), REQUIRED_PROMPTS)


if __name__ == "__main__":
    unittest.main()
