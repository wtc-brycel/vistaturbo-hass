from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


path = "vista128_bridge/app/vista_bridge/message_handler.py"
replace_once(
    path,
    '''        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n''',
    '''        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n        self._history_occurrences: dict[str, int] = {}\n''',
    "history occurrence map",
)
replace_once(
    path,
    '''        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""\n        if self.event_store is not None and self.event_store.record(\n            event, source="history", received_at=received_at, descriptor=descriptor\n        ):\n            self._history_dump_inserted += 1\n''',
    '''        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""\n        fingerprint = EventStore.fingerprint(event)\n        occurrence = self._history_occurrences.get(fingerprint, 0) + 1\n        self._history_occurrences[fingerprint] = occurrence\n        if self.event_store is not None and self.event_store.record(\n            event,\n            source="history",\n            received_at=received_at,\n            descriptor=descriptor,\n            occurrence=occurrence,\n        ):\n            self._history_dump_inserted += 1\n''',
    "history occurrence record",
)
replace_once(
    path,
    '''        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n\n    def _handle_arming_status''',
    '''        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n        self._history_occurrences.clear()\n\n    def _handle_arming_status''',
    "history occurrence reset",
)
replace_once(
    path,
    '''        LOG.info("Zone %03d descriptor: %s", report.zone, report.descriptor)\n        self.mqtt.publish_zone_discovery(zone)\n''',
    '''        LOG.info("Zone %03d descriptor: %s", report.zone, report.descriptor)\n        if self.event_store is not None:\n            updated = self.event_store.update_descriptor(report.zone, report.descriptor)\n            if updated:\n                self.publish_event_history_snapshot()\n        self.mqtt.publish_zone_discovery(zone)\n''',
    "descriptor backfill",
)

path = "vista128_bridge/tests/test_event_store.py"
p = Path(path)
s = p.read_text()
s = s.replace(
    '''            self.assertFalse(\n                store.record(\n                    event,\n                    source="history",\n                    received_at="2026-08-17T10:00:00-04:00",\n                )\n            )\n''',
    '''            self.assertFalse(\n                store.record(\n                    event,\n                    source="history",\n                    received_at="2026-08-17T10:00:00-04:00",\n                    occurrence=1,\n                )\n            )\n''',
    1,
)
anchor = '''    def test_history_dump_metadata_persists(self):\n'''
if anchor not in s:
    raise SystemExit("missing event-store test anchor")
s = s.replace(anchor, '''    def test_repeated_same_minute_events_are_preserved_by_occurrence(self):\n        with tempfile.TemporaryDirectory() as tmp:\n            store = EventStore(os.path.join(tmp, "events.sqlite3"))\n            event = sample_event()\n            self.assertTrue(store.record(event, source="history", received_at="2026-08-17T10:00:00-04:00", occurrence=1))\n            self.assertTrue(store.record(event, source="history", received_at="2026-08-17T10:00:01-04:00", occurrence=2))\n            self.assertFalse(store.record(event, source="history", received_at="2026-08-17T10:01:00-04:00", occurrence=1))\n            self.assertEqual(store.stats().count, 2)\n            self.assertEqual([row["occurrence"] for row in store.recent(20)], [2, 1])\n\n    def test_descriptor_backfill_updates_existing_rows(self):\n        with tempfile.TemporaryDirectory() as tmp:\n            store = EventStore(os.path.join(tmp, "events.sqlite3"))\n            event = sample_event()\n            event = SystemEvent(**{**event.__dict__, "zone": 27})\n            store.record(event, source="history", received_at="2026-08-17T10:00:00-04:00", occurrence=1)\n            self.assertEqual(store.update_descriptor(27, "FRONT DOOR"), 1)\n            self.assertEqual(store.recent(1)[0]["descriptor"], "FRONT DOOR")\n\n''' + anchor, 1)
p.write_text(s)
