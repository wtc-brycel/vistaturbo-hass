import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import (  # noqa: E402
    EVENT_LOG_QUERY,
    STARTUP_QUERIES,
    STATE_SYNC_QUERIES,
    build_keypad_display_query,
    identify_message,
    parse_arming_status,
    parse_event_log_entry,
    parse_keypad_display,
    parse_system_event,
    parse_zone_descriptor,
    parse_zone_partition,
    parse_zone_status,
    validate_packet,
)


class ProtocolTests(unittest.TestCase):
    def test_startup_queries_are_exact_and_crlf_terminated(self):
        self.assertEqual(
            [(query.name, query.data) for query in STARTUP_QUERIES],
            [
                ("arming_status", b"08as0064\r\n"),
                ("zone_status", b"08zs004B\r\n"),
                ("zone_partition", b"08ZP008E\r\n"),
                ("zone_descriptor", b"08ZD009A\r\n"),
            ],
        )

    def test_event_log_query_is_exact_and_long_running(self):
        self.assertEqual(EVENT_LOG_QUERY.name, "event_log")
        self.assertEqual(EVENT_LOG_QUERY.data, b"08LD00A8\r\n")
        self.assertEqual(EVENT_LOG_QUERY.timeout_seconds, 45)
        self.assertFalse(EVENT_LOG_QUERY.required)

    def test_periodic_state_sync_is_dynamic_state_only(self):
        self.assertEqual(
            [(query.name, query.data) for query in STATE_SYNC_QUERIES],
            [
                ("arming_status", b"08as0064\r\n"),
                ("zone_status", b"08zs004B\r\n"),
            ],
        )

    def test_identifies_known_messages(self):
        self.assertEqual(identify_message(b"08OK009E"), "ready")
        self.assertEqual(identify_message(b"10ASDDDDDDDD008B"), "arming_status")
        self.assertEqual(identify_message(b"49ZS1000"), "zone_status")
        self.assertEqual(identify_message(b"69ZS0000"), "zone_status")
        self.assertEqual(identify_message(b"49ZP1100"), "zone_partition")
        self.assertEqual(identify_message(b'0DZD000""00BA'), "zone_descriptor")
        self.assertEqual(
            identify_message(b"29kd\xd01   DISARMED   BYPAS-RDY TO ARM100CD"),
            "keypad_display",
        )
        self.assertEqual(identify_message(b"1BnqSOMETHING"), "system_event")
        self.assertEqual(identify_message(b"08XF009A"), "communication_off")
        self.assertEqual(identify_message(b"10DC000000000000"), "display_changed")
        self.assertEqual(identify_message(b"1BldSOMETHING"), "event_log_entry")
        self.assertEqual(identify_message(b"08lc0069"), "event_log_complete")

    def test_unknown_data_is_preserved_as_unknown(self):
        self.assertEqual(identify_message(b"weird"), "unknown")

    def test_packet_validation_matches_captured_panel_packets(self):
        for packet in (
            b"08OK009E",
            b"10ASDDDDDDDD008B",
            b"1BnqB7000002121031508260086",
            b"49ZS100000000000000000000800000000000800000000880000000000000000000000035",
            b"49ZP10011110000000000011111111111011011111010111000000000000000000000003E",
            b"29kd\xd01   DISARMED   BYPAS-RDY TO ARM100CD",
        ):
            with self.subTest(packet=packet):
                validation = validate_packet(packet)
                self.assertTrue(validation.valid)
                self.assertTrue(validation.length_ok)
                self.assertTrue(validation.checksum_ok)

    def test_packet_validation_rejects_corruption(self):
        validation = validate_packet(b"10ASADDDDDDD008B")
        self.assertFalse(validation.valid)
        self.assertTrue(validation.length_ok)
        self.assertFalse(validation.checksum_ok)

    def test_build_keypad_display_query_matches_captured_request(self):
        query = build_keypad_display_query(1)
        self.assertEqual(query.name, "keypad_display_p1")
        self.assertEqual(query.partition, 1)
        self.assertEqual(query.data, b"09KD10077\r\n")
        with self.assertRaises(ValueError):
            build_keypad_display_query(0)

    def test_parse_captured_keypad_display(self):
        packet = b"29kd\xd01   DISARMED   BYPAS-RDY TO ARM100CD"
        report = parse_keypad_display(packet)
        self.assertIsNotNone(report)
        self.assertEqual(report.line_1, "P1   DISARMED   ")
        self.assertEqual(report.line_2, "BYPAS-RDY TO ARM")
        self.assertTrue(report.backlight)
        self.assertTrue(report.ready_led)
        self.assertFalse(report.trouble_led)
        self.assertFalse(report.armed_led)
        self.assertEqual(report.led_status, 0x1)
        self.assertEqual(report.raw_display[0], 0xD0)

    def test_parse_arming_status(self):
        report = parse_arming_status(b"10ASDDDDDDDD008B")
        self.assertIsNotNone(report)
        self.assertEqual(report.raw_modes, tuple("DDDDDDDD"))

    def test_69zs_is_not_used_for_zone_state(self):
        packet = b"69ZS0000000000000000000090000000000082000000099000000000000000000000000000000000000000000000000000000002F"
        self.assertTrue(validate_packet(packet).valid)
        self.assertIsNone(parse_zone_status(packet))

    def test_parse_captured_zone_status(self):
        report = parse_zone_status(
            b"49ZS100000000000000000000800000000000800000000880000000000000000000000035"
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.block, 1)
        self.assertEqual(len(report.statuses), 64)
        self.assertEqual(report.statuses[20], 8)
        self.assertEqual(report.statuses[32], 8)
        self.assertEqual(report.statuses[41], 8)
        self.assertEqual(report.statuses[42], 8)
        self.assertEqual(sum(v != 0 for v in report.statuses), 4)

    def test_parse_captured_zone_partition(self):
        report = parse_zone_partition(
            b"49ZP10011110000000000011111111111011011111010111000000000000000000000003E"
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.block, 1)
        self.assertEqual(len(report.partitions), 64)
        self.assertEqual(report.partitions[0], 0)
        self.assertEqual(report.partitions[2], 1)

    def test_parse_captured_system_event(self):
        event = parse_system_event(b"1BnqB7000002121031508260086")
        self.assertIsNotNone(event)
        self.assertEqual(event.code, "B7")
        self.assertEqual(event.description, "Arm STAY")
        self.assertEqual(event.zone, 0)
        self.assertEqual(event.user, 2)
        self.assertEqual(event.partition, 1)
        self.assertEqual(event.minute, 21)
        self.assertEqual(event.hour, 3)
        self.assertEqual(event.day, 15)
        self.assertEqual(event.month, 8)
        self.assertEqual(event.year, 26)
        self.assertEqual(event.panel_timestamp, "2026-08-15T03:21")

    def test_parse_historical_event_log_entry(self):
        packet = make_packet("ldB70000021210315082600")
        self.assertTrue(validate_packet(packet).valid)
        self.assertEqual(identify_message(packet), "event_log_entry")
        event = parse_event_log_entry(packet)
        self.assertIsNotNone(event)
        self.assertEqual(event.code, "B7")
        self.assertEqual(event.user, 2)
        self.assertEqual(event.partition, 1)
        self.assertEqual(event.panel_timestamp, "2026-08-15T03:21")

    def test_parse_zone_descriptor_and_end_marker(self):
        packet = make_packet('ZD003"OFFICE WINDOW"00')
        report = parse_zone_descriptor(packet)
        self.assertIsNotNone(report)
        self.assertEqual(report.zone, 3)
        self.assertEqual(report.descriptor, "OFFICE WINDOW")
        self.assertFalse(report.end)

        end = parse_zone_descriptor(b'0DZD000""00BA')
        self.assertIsNotNone(end)
        self.assertTrue(end.end)

    def test_lowercase_zone_descriptor_packet_is_identified_and_decoded(self):
        packet = b'22zd003"GARAGE HEAT DETECTOR "0004'
        self.assertEqual(identify_message(packet), "zone_descriptor")
        report = parse_zone_descriptor(packet)
        self.assertIsNotNone(report)
        self.assertEqual(report.zone, 3)
        self.assertEqual(report.descriptor, "GARAGE HEAT DETECTOR")

    def test_descriptor_query_is_long_running_optional_metadata(self):
        query = next(q for q in STARTUP_QUERIES if q.name == "zone_descriptor")
        self.assertEqual(query.timeout_seconds, 45)
        self.assertFalse(query.required)

    def test_parse_captured_bypass_event(self):
        packet = b"1Bnq0503400214423150826008C"
        validation = validate_packet(packet)
        self.assertTrue(validation.valid)
        event = parse_system_event(packet)
        self.assertIsNotNone(event)
        self.assertEqual(event.code, "05")
        self.assertEqual(event.description, "Bypass")
        self.assertEqual(event.zone, 34)
        self.assertEqual(event.user, 2)
        self.assertEqual(event.partition, 1)
        self.assertEqual(event.panel_timestamp, "2026-08-15T23:44")

    def test_actual_lowercase_zone_descriptor_end_marker(self):
        packet = b'0Dzd000""007A'
        self.assertTrue(validate_packet(packet).valid)
        self.assertEqual(identify_message(packet), "zone_descriptor")
        report = parse_zone_descriptor(packet)
        self.assertIsNotNone(report)
        self.assertTrue(report.end)


def make_packet(body_without_length_and_checksum: str) -> bytes:
    total_length = 2 + len(body_without_length_and_checksum) + 2
    prefix = f"{total_length:02X}" + body_without_length_and_checksum
    checksum = (-sum(prefix.encode("ascii"))) & 0xFF
    return (prefix + f"{checksum:02X}").encode("ascii")


if __name__ == "__main__":
    unittest.main()
