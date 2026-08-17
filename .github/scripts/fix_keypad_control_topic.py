from pathlib import Path

path = Path("vista128_bridge/app/vista_bridge/mqtt_client.py")
text = path.read_text()
old = '        prefix = self.topic(f"{category}/")\n'
new = '        prefix = self.topic(category) + "/"\n'
if old not in text:
    raise RuntimeError("control topic parser anchor not found")
path.write_text(text.replace(old, new, 1))
