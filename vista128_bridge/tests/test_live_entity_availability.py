import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.mqtt_discovery import (  # noqa: E402
    keypad_config,
    panel_alarm_availability,
    partition_config,
    zone_condition_configs,
)
from vista_bridge.state import ZoneState  # noqa: E402


def topic(suffix: str) -> str:
    return f"vista128/{suffix}"


class LiveEntityAvailabilityTests(unittest.TestCase):
    def test_live_entities_do_not_depend_on_panel_state_fresh(self) -> None:
        zone = ZoneState(zone=3, partition=1, descriptor="GARAGE HEAT DETECTOR")
        configs = [
            partition_config(1, topic),
            keypad_config(1, topic),
            *zone_condition_configs(zone, topic).values(),
        ]
        for config in configs:
            topics = {item["topic"] for item in config["availability"]}
            self.assertIn("vista128/bridge/availability", topics)
            self.assertIn("vista128/panel/connected", topics)
            self.assertNotIn("vista128/panel/state_fresh", topics)

    def test_alarm_entities_keep_alarm_specific_fail_safe_availability(self) -> None:
        availability = panel_alarm_availability("fire", topic)["availability"]
        topics = {item["topic"] for item in availability}
        self.assertIn("vista128/alarm/fire/available", topics)


if __name__ == "__main__":
    unittest.main()
