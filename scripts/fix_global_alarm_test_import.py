from pathlib import Path

path = Path("vista128_bridge/tests/test_readiness.py")
text = path.read_text(encoding="utf-8")
old = "from vista_bridge.protocol import KeypadDisplayReport, SystemEvent\n"
new = "from vista_bridge.protocol import ArmingStatusReport, KeypadDisplayReport, SystemEvent\n"
if old not in text:
    raise SystemExit("missing readiness import anchor")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
