import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.release_validation import (
    ReleaseValidationError,
    create_release_bundle,
    load_release_metadata,
    release_metadata_matches,
    successful_required_checks,
    tag_points_to_commit,
)


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "release").mkdir()
        (self.root / "frontend").mkdir()
        (self.root / "release" / "notes.md").write_text("notes\n", encoding="utf-8")
        (self.root / "frontend" / "vista-keypad-card.js").write_text("card\n", encoding="utf-8")
        (self.root / "frontend" / "vista-keypad-simulator.html").write_text(
            "simulator\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_metadata(self, data):
        path = self.root / "release" / "rc.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_metadata_and_fixed_name_bundle(self):
        path = self.write_metadata(
            {"tag": "v1.2.3-rc.4", "name": "Vista RC", "notes": "release/notes.md"}
        )
        metadata = load_release_metadata(path)
        manifest = create_release_bundle(metadata, self.root / "bundle", "a" * 40)
        self.assertEqual(manifest["tag"], "v1.2.3-rc.4")
        self.assertEqual({p.name for p in (self.root / "bundle").iterdir()}, {
            "manifest.json", "notes.md", "vista-keypad-card.js", "vista-keypad-simulator.html"
        })

    def test_rejects_unexpected_keys_and_unsafe_tag(self):
        path = self.write_metadata(
            {"tag": "main", "name": "Vista RC", "notes": "release/notes.md", "extra": 1}
        )
        with self.assertRaises(ReleaseValidationError):
            load_release_metadata(path)

    def test_rejects_absolute_traversal_and_non_markdown_notes(self):
        for notes in ["/tmp/notes.md", "release/../frontend/vista-keypad-card.js", "release/rc.json"]:
            path = self.write_metadata(
                {"tag": "v1.2.3-rc.4", "name": "Vista RC", "notes": notes}
            )
            with self.subTest(notes=notes), self.assertRaises(ReleaseValidationError):
                load_release_metadata(path)

    def test_rejects_symlink_escaping_release_directory(self):
        outside = self.root / "outside.md"
        outside.write_text("secret\n", encoding="utf-8")
        notes = self.root / "release" / "escaped.md"
        try:
            notes.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        path = self.write_metadata(
            {"tag": "v1.2.3-rc.4", "name": "Vista RC", "notes": "release/escaped.md"}
        )
        with self.assertRaises(ReleaseValidationError):
            load_release_metadata(path)

    def test_required_checks_need_newest_actions_check_to_succeed(self):
        checks = [
            {"id": 10, "name": "test", "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"}},
            {"id": 11, "name": "frontend-render", "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"}},
        ]
        self.assertTrue(successful_required_checks(checks))
        checks.append(
            {"id": 12, "name": "test", "status": "completed", "conclusion": "failure", "app": {"slug": "github-actions"}}
        )
        self.assertFalse(successful_required_checks(checks))

    def test_required_checks_reject_missing_pending_or_untrusted_checks(self):
        self.assertFalse(successful_required_checks([]))
        self.assertFalse(successful_required_checks([
            {"id": 1, "name": "test", "status": "completed", "conclusion": "success", "app": {"slug": "other"}},
            {"id": 2, "name": "frontend-render", "status": "queued", "conclusion": None, "app": {"slug": "github-actions"}},
        ]))

    def test_mismatched_tag_and_release_identity_is_rejected(self):
        expected = "a" * 40
        self.assertTrue(tag_points_to_commit(expected, expected))
        self.assertFalse(tag_points_to_commit("b" * 40, expected))
        self.assertTrue(release_metadata_matches(
            {"tag_name": "v1.2.3-rc.4", "prerelease": True, "draft": False},
            "v1.2.3-rc.4",
        ))
        self.assertFalse(release_metadata_matches(
            {"tag_name": "v1.2.3-rc.4", "prerelease": True, "draft": False},
            "v9.9.9-rc.1",
        ))
        self.assertFalse(release_metadata_matches(
            {"tag_name": "v1.2.3-rc.4", "prerelease": False, "draft": False},
            "v1.2.3-rc.4",
        ))


if __name__ == "__main__":
    unittest.main()
