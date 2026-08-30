import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.event_codes import EVENT_DESCRIPTIONS, classify_alarm_event  # noqa: E402


class AlarmEventClassificationTests(unittest.TestCase):
    def test_auxiliary_alarm_and_restore_are_canonical_auxiliary(self):
        self.assertEqual(classify_alarm_event("B1"), ("auxiliary", "alarm"))
        self.assertEqual(classify_alarm_event("B2"), ("auxiliary", "restore"))

    def test_burglary_families_are_not_auxiliary(self):
        for start, restore in (
            ("41", "42"),
            ("51", "52"),
            ("61", "62"),
            ("71", "72"),
            ("81", "82"),
        ):
            with self.subTest(start=start):
                self.assertEqual(classify_alarm_event(start), ("burglary", "alarm"))
                self.assertEqual(classify_alarm_event(restore), ("burglary", "restore"))

    def test_24_hour_zone_description_stays_literal_while_semantics_are_burglary(self):
        self.assertEqual(EVENT_DESCRIPTIONS["61"], "24 Hour Zone Alarm")
        self.assertEqual(EVENT_DESCRIPTIONS["62"], "24 Hour Zone Alarm Restore")
        self.assertEqual(classify_alarm_event("61"), ("burglary", "alarm"))
        self.assertEqual(classify_alarm_event("62"), ("burglary", "restore"))

    def test_audible_panic_is_not_burglary_or_auxiliary(self):
        self.assertEqual(classify_alarm_event("31"), ("panic_audible", "alarm"))
        self.assertEqual(classify_alarm_event("32"), ("panic_audible", "restore"))

    def test_non_alarm_event_has_no_alarm_class(self):
        self.assertEqual(classify_alarm_event("F5"), (None, None))


if __name__ == "__main__":
    unittest.main()
