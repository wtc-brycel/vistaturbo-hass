import tempfile
import unittest
from pathlib import Path

from scripts.check_repository_security import check_repository


class RepositorySecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / "release").mkdir()
        (self.root / "frontend").mkdir()
        (self.root / "release" / "rc.json").write_text(
            '{"tag":"v1.2.3-rc.4","name":"Vista RC","notes":"release/notes.md"}',
            encoding="utf-8",
        )
        (self.root / "release" / "notes.md").write_text("notes\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_workflow(self, text):
        (self.root / ".github" / "workflows" / "tests.yml").write_text(text, encoding="utf-8")

    def test_passes_immutable_read_only_workflow(self):
        self.write_workflow(
            """permissions:\n  contents: read\njobs:\n  test:\n    steps:\n      - name: Check out\n        uses: actions/checkout@1111111111111111111111111111111111111111 # v4.2.2\n        with:\n          persist-credentials: false\n      - name: Set up Python\n        uses: actions/setup-python@2222222222222222222222222222222222222222 # v5.6.0\n"""
        )
        self.assertEqual(check_repository(self.root), [])

    def test_rejects_mutable_actions_write_and_persistent_checkout(self):
        self.write_workflow(
            """permissions:\n  contents: write\njobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n"""
        )
        errors = check_repository(self.root)
        self.assertTrue(any("immutable ref" in error or "full commit SHA" in error for error in errors))
        self.assertTrue(any("contents: write" in error for error in errors))
        self.assertTrue(any("persist-credentials" in error for error in errors))

    def test_rejects_latest_production_base(self):
        (self.root / "Dockerfile").write_text("FROM example/base:latest\n", encoding="utf-8")
        self.write_workflow(
            """permissions:\n  contents: read\njobs:\n  test:\n    steps:\n      - uses: actions/checkout@1111111111111111111111111111111111111111 # v4.2.2\n        with:\n          persist-credentials: false\n"""
        )
        self.assertTrue(any(":latest" in error for error in check_repository(self.root)))


if __name__ == "__main__":
    unittest.main()
