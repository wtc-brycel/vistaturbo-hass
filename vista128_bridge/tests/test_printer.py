import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_settings  # noqa: E402
from vista_bridge.printer import (  # noqa: E402
    TransPortEventPrinter,
    format_event_receipt,
    panel_clock_offset_seconds,
)
from vista_bridge.protocol import parse_system_event  # noqa: E402


CAPTURED_EVENT = parse_system_event(b"1BnqB7000002121031508260086")
assert CAPTURED_EVENT is not None


class ReceiptFormattingTests(unittest.TestCase):
    def test_receipt_is_plain_32_column_text(self):
        text = format_event_receipt(
            sequence=7,
            event=CAPTURED_EVENT,
            descriptor="",
            received_at="2026-08-15T05:27:38+00:00",
            width=32,
            timezone_name="America/New_York",
        )
        self.assertIn("VISTA EVENT #000007", text)
        self.assertIn("ARM STAY [B7]", text)
        self.assertIn("P1 U002", text)
        self.assertIn("PANEL 2026-08-15 03:21", text)
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\x00", text)
        for line in text.splitlines():
            self.assertLessEqual(len(line), 32)

    def test_panel_clock_offset_uses_configured_timezone(self):
        offset = panel_clock_offset_seconds(
            CAPTURED_EVENT,
            "2026-08-15T05:21:00+00:00",
            "America/New_York",
        )
        self.assertEqual(offset, 7200)


class TransPortPrinterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.received = bytearray()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _server(self, status: int):
        async def handler(reader, writer):
            header = await reader.readuntil(b"\r\n\r\n")
            lines = header.decode("ascii").split("\r\n")
            length = 0
            for line in lines:
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1].strip())
            self.received.extend(await reader.readexactly(length))
            writer.write(
                f"HTTP/1.1 {status} Test\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode(
                    "ascii"
                )
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        return server, port

    async def test_http_204_marks_job_complete(self):
        server, port = await self._server(204)
        try:
            printer = TransPortEventPrinter(
                make_settings(
                    spool_path=os.path.join(self.tmp.name, "queue.db"),
                    printer_enabled=True,
                    printer_port=port,
                )
            )
            job_id = printer.enqueue_event(
                event=CAPTURED_EVENT,
                descriptor="",
                received_at="2026-08-15T05:27:38+00:00",
            )
            self.assertIsNotNone(job_id)
            job = printer.store.next_pending()
            self.assertIsNotNone(job)
            await printer._deliver(job)
            self.assertEqual(printer.metrics.completed, 1)
            self.assertEqual(printer.metrics.queue_depth, 0)
            self.assertIn(b"ARM STAY [B7]", bytes(self.received))
            printer.close()
        finally:
            server.close()
            await server.wait_closed()

    async def test_http_503_is_uncertain_and_not_pending(self):
        server, port = await self._server(503)
        try:
            printer = TransPortEventPrinter(
                make_settings(
                    spool_path=os.path.join(self.tmp.name, "queue.db"),
                    printer_enabled=True,
                    printer_port=port,
                )
            )
            printer.enqueue_event(
                event=CAPTURED_EVENT,
                descriptor="",
                received_at="2026-08-15T05:27:38+00:00",
            )
            job = printer.store.next_pending()
            self.assertIsNotNone(job)
            await printer._deliver(job)
            self.assertEqual(printer.metrics.uncertain, 1)
            self.assertEqual(printer.metrics.queue_depth, 0)
            self.assertIsNone(printer.store.next_pending())
            printer.close()
        finally:
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
