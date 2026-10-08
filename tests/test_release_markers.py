import importlib.util
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "all" / "channel_manager" / "release_markers.py"
spec = importlib.util.spec_from_file_location("channel_release_markers", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseMarkerTests(unittest.TestCase):
    def test_marker_ref_and_selector_are_independent(self):
        branch, markers = module.parse_release_markers([
            "master",
            {"ref": "st-build-3998", "sublime_text": "<=3999", "python_versions": ["3.3"]},
            {"ref": "st-build-4999", "sublime_text": "4000 - 4999", "python_versions": ["3.8"]},
        ])

        self.assertEqual(branch, "master")
        self.assertEqual(markers[0]["ref"], "st-build-3998")
        self.assertEqual(markers[0]["ceiling"], 3999)
        self.assertEqual(markers[1]["ceiling"], 4999)

    def test_snapshots_of_one_generation_may_share_a_selector(self):
        branch, markers = module.parse_release_markers([
            {"ref": "st-build-3998", "sublime_text": "<=3999", "python_versions": ["3.3"]},
            {"ref": "st-build-3999", "sublime_text": "<=3999", "python_versions": ["3.3"]},
        ])

        self.assertIsNone(branch)
        self.assertEqual([marker["ceiling"] for marker in markers], [3999, 3999])

    def test_rejects_selector_that_reaches_older_generation(self):
        with self.assertRaisesRegex(ValueError, "outside its Sublime generation"):
            module.parse_release_markers([
                {"ref": "st-build-4999", "sublime_text": "<=4999", "python_versions": ["3.8"]},
            ])

    def test_rejects_unverified_host_and_legacy_numeric_ref(self):
        with self.assertRaisesRegex(ValueError, "python_versions"):
            module.parse_release_markers([
                {"ref": "st-build-3999", "sublime_text": "<=3999"},
            ])
        with self.assertRaisesRegex(ValueError, "numeric"):
            module.parse_release_markers(["3999"])

    def test_release_tag_cleanup_preserves_build_markers(self):
        self.assertEqual(
            module.mutable_release_tags([
                "1.2.3", "st-build-3999", "st3-1.0.109", "3999", "v1.3.0", "",
            ]),
            ["1.2.3", "v1.3.0"],
        )

    def test_historical_markers_do_not_become_current_releases(self):
        self.assertEqual(module.latest_semantic_tag(["3999", "st-build-3999", "st3-1.0.109"]), "master")
        self.assertEqual(
            module.latest_semantic_tag(["1.0.0", "3999", "st-build-3999", "st3-1.0.109", "1.1.1"]),
            "1.1.1",
        )

    def test_no_tag_repository_uses_declared_fork_branch(self):
        self.assertEqual(module.declared_main_branch("main->main,"), "main")
        self.assertEqual(module.declared_main_branch("master->release,main->main"), "release")
        self.assertEqual(module.declared_main_branch(""), "master")


if __name__ == "__main__":
    unittest.main()
