from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent


class IngressKeypadBundleTests(unittest.TestCase):
    def test_ingress_uses_exact_lovelace_keypad_bundle(self):
        lovelace = REPOSITORY_ROOT / "frontend" / "vista-keypad-card.js"
        ingress = (
            ROOT
            / "app"
            / "vista_bridge"
            / "admin_frontend"
            / "vista-keypad-card.js"
        )
        self.assertEqual(lovelace.read_bytes(), ingress.read_bytes())


if __name__ == "__main__":
    unittest.main()
