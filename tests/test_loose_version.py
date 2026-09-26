import importlib.util
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "all" / "channel_manager" / "loose_version.py"
spec = importlib.util.spec_from_file_location("channel_loose_version", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
LooseVersion = module.LooseVersion


class LooseVersionTests(unittest.TestCase):
    def test_date_and_prerelease_order(self):
        self.assertGreater(LooseVersion("2026.09.27"), LooseVersion("2026.09.26"))
        self.assertGreater(LooseVersion("1.5.2b2"), LooseVersion("1.5.2b1"))
        self.assertGreater(LooseVersion("v1.6a"), LooseVersion("v1.5"))
        self.assertLess(LooseVersion("1.0"), LooseVersion("1.0.0"))

    def test_string_comparison_and_parsing(self):
        version = LooseVersion("2026.09.26")
        self.assertEqual(version.version, [2026, 9, 26])
        self.assertEqual(str(version), "2026.09.26")
        self.assertEqual(repr(version), "LooseVersion ('2026.09.26')")
        self.assertEqual(version, "2026.09.26")

    def test_incompatible_components_keep_original_error(self):
        with self.assertRaises(TypeError):
            LooseVersion("1.2a") < LooseVersion("1.2.0")


if __name__ == "__main__":
    unittest.main()
