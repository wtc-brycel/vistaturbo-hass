from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from vista_bridge.version import VERSION  # noqa: E402


class PackageQualityTests(unittest.TestCase):
    def test_manifest_version_matches_runtime_version(self):
        manifest = (ROOT / "config.yaml").read_text()
        match = re.search(r'^version:\s*"([^"]+)"', manifest, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), VERSION)

    def test_ai_disclosure_is_present(self):
        marker = "This App was made with the use of AI - ChatGPT Codex, specifically -"
        for name in ("README.md", "DOCS.md"):
            with self.subTest(path=name):
                self.assertIn(marker, (ROOT / name).read_text())

    def test_shipped_text_has_no_em_dash(self):
        suffixes = {".py", ".md", ".yaml", ".sh", ".txt"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("\u2014", path.read_text(errors="ignore"))


if __name__ == "__main__":
    unittest.main()
