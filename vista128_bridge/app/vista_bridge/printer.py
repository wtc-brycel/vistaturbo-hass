from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import textwrap
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .printer_store import PrintJob, PrintQueueStore
from .protocol import SystemEvent

LOG = logging.getLogger(__name__)
MAX_JOB_BYTES = 8192


@dataclass
class PrinterMetrics:
    status: str = "disabled"
    completed: int = 0
    uncertain: int = 0
    failed: int = 0
    dropped: int = 0
    queue_depth: int = 0
    last_error: str = ""
    last_completed_at: str = ""


def _zoneinfo(name: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        LOG.warning("Timezone %r not found; using UTC", name)
        return timezone.utc


def panel_clock_offset_seconds(
    event: SystemEvent,
    received_at: str,
    timezone_name: str,
) -> int | None:
    """Return panel time minus receive time in seconds."""
    try:
        received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        panel_time = datetime(
            2000 + event.year,
            event.month,
            event.day,
            event.hour,
            event.minute,
            tzinfo=_zoneinfo(timezone_name),
        )
    except (ValueError, TypeError):
        return None
    delta = panel_time.astimezone(timezone.utc) - received.astimezone(timezone.utc)
    return int(delta.total_seconds())


def _wrap_line(value: str, width: int) -> list[str]:
    return textwrap.wrap(
        " ".join(value.split()),
        width=max(8, width),
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def format_event_receipt(
    *,
    sequence: int,
    event: SystemEvent,
    descriptor: str,
    received_at: str,
    width: int,
    timezone_name: str,
) -> str:
    """Render one continuous-text event record."""
    width = max(24, min(width, 64))
    try:
        received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        received_text = received.astimezone(_zoneinfo(timezone_name)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        received_text = received_at[:19]

    lines = [f"VISTA EVENT #{sequence:06d}", received_text]
    lines.extend(_wrap_line(f"{event.description.upper()} [{event.code}]", width))

    details = []
    if event.partition:
        details.append(f"P{event.partition}")
    if event.zone:
        details.append(f"Z{event.zone:03d}")
    if event.user:
        details.append(f"U{event.user:03d}")
    if details:
        lines.append(" ".join(details))

    if event.zone and descriptor:
        lines.extend(_wrap_line(descriptor.upper(), width))
    if event.panel_timestamp:
        lines.append(f"PANEL {event.panel_timestamp.replace('T', ' ')}")

    lines.append("-" * width)
    return "\n".join(line[:width] for line in lines) + "\n"


class TransPortEventPrinter:
    """Queue and deliver VISTA event receipts to TransPort."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings.printer
        self.panel_timezone = settings.panel.timezone
        self.enabled = self.settings.enabled
        self.metrics = PrinterMetrics(status="initializing" if self.enabled else "disabled")
        self.store = PrintQueueStore(self.settings.spool_path) if self.enabled else None
        if self.store is not None:
            self._refresh_queue_depth()
            self.metrics.status = "idle"

    def close(self) -> None:
        if self.store is not None:
            self.store.close()
            self.store = None

    def _refresh_queue_depth(self) -> None:
        self.metrics.queue_depth = self.store.queue_depth() if self.store else 0

    def enqueue_event(
        self,
        *,
        event: SystemEvent,
        descriptor: str,
        received_at: str,
    ) -> int | None:
        if not self.enabled or self.store is None:
            return None

        self._refresh_queue_depth()
        if self.metrics.queue_depth >= self.settings.queue_max:
            self.metrics.dropped += 1
            self.metrics.status = "queue_full"
            self.metrics.last_error = f"print queue limit {self.settings.queue_max} reached"
            LOG.error("TransPort receipt not queued: %s", self.metrics.last_error)
            return None

        sequence = self.store.create(received_at, event.code)
        payload = format_event_receipt(
            sequence=sequence,
            event=event,
            descriptor=descriptor,
            received_at=received_at,
            width=self.settings.width,
            timezone_name=self.panel_timezone,
        ).encode("utf-8")
        if len(payload) > MAX_JOB_BYTES:
            self.store.delete(sequence)
            self.metrics.failed += 1
            self.metrics.last_error = "formatted receipt exceeds TransPort limit"
            LOG.error("TransPort receipt %d rejected: %s", sequence, self.metrics.last_error)
            return None

        self.store.set_payload(sequence, payload)
        self._refresh_queue_depth()
        LOG.info("Queued TransPort receipt #%06d for event %s", sequence, event.code)
        return sequence

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.enabled:
            return
        try:
            while not stop_event.is_set():
                job = self.store.next_pending() if self.store else None
                if job is None:
                    self.metrics.status = "idle"
                    self._refresh_queue_depth()
                    await self._wait(stop_event, 0.5)
                    continue
                await self._deliver(job)
        finally:
            self.close()

    async def _deliver(self, job: PrintJob) -> None:
        self.metrics.status = "connecting"
        writer: asyncio.StreamWriter | None = None
        request_started = False
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.settings.host, self.settings.http_port),
                timeout=self.settings.timeout_seconds,
            )
        except (asyncio.TimeoutError, OSError) as exc:
            await self._safe_retry(job, exc)
            return

        try:
            request = self._build_request(job.payload)
            self.metrics.status = "printing"
            request_started = True
            writer.write(request)
            await asyncio.wait_for(writer.drain(), timeout=self.settings.timeout_seconds)
            status_code = await self._read_status(reader)
            self._apply_http_result(job.job_id, status_code)
        except asyncio.CancelledError:
            if request_started:
                self._mark_uncertain(job.job_id, "shutdown after submission began")
            raise
        except (asyncio.TimeoutError, OSError, RuntimeError) as exc:
            if request_started:
                error = f"response lost after submission: {type(exc).__name__}: {exc}"
                self._mark_uncertain(job.job_id, error)
            else:
                await self._safe_retry(job, exc)
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    def _build_request(self, payload: bytes) -> bytes:
        headers = (
            "POST /print HTTP/1.1\r\n"
            f"Host: {self.settings.host}:{self.settings.http_port}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n\r\n"
        )
        return headers.encode("ascii") + payload

    async def _read_status(self, reader: asyncio.StreamReader) -> int:
        status_line = await asyncio.wait_for(
            reader.readline(), timeout=self.settings.timeout_seconds
        )
        parts = status_line.decode("ascii", errors="replace").strip().split()
        if len(parts) < 2 or not parts[1].isdigit():
            raise RuntimeError(f"invalid HTTP response: {status_line!r}")
        while True:
            line = await asyncio.wait_for(
                reader.readline(), timeout=self.settings.timeout_seconds
            )
            if line in {b"", b"\r\n", b"\n"}:
                break
        return int(parts[1])

    def _apply_http_result(self, job_id: int, status_code: int) -> None:
        if status_code == 204:
            self._mark_complete(job_id)
            LOG.info("TransPort receipt #%06d accepted", job_id)
            return
        if 400 <= status_code < 500:
            error = f"TransPort rejected receipt with HTTP {status_code}"
            self._mark_failed(job_id, error)
            LOG.error("Receipt #%06d failed: %s", job_id, error)
            return
        error = f"TransPort returned HTTP {status_code} after submission"
        self._mark_uncertain(job_id, error)
        LOG.error("Receipt #%06d uncertain: %s", job_id, error)

    async def _safe_retry(self, job: PrintJob, exc: BaseException) -> None:
        if self.store is None:
            return
        error = f"connect failed: {type(exc).__name__}: {exc}"
        self.store.record_attempt_error(job.job_id, error)
        self.metrics.status = "offline"
        self.metrics.last_error = error
        self._refresh_queue_depth()
        LOG.warning(
            "TransPort receipt #%06d not sent; retrying in %ss: %s",
            job.job_id,
            self.settings.retry_seconds,
            error,
        )
        await asyncio.sleep(self.settings.retry_seconds)

    def _mark_complete(self, job_id: int) -> None:
        if self.store is None:
            return
        completed_at = self.store.mark_complete(job_id)
        self.metrics.completed += 1
        self.metrics.last_completed_at = completed_at
        self.metrics.last_error = ""
        self.metrics.status = "idle"
        self._refresh_queue_depth()

    def _mark_uncertain(self, job_id: int, error: str) -> None:
        if self.store is None:
            return
        self.store.mark_uncertain(job_id, error)
        self.metrics.uncertain += 1
        self.metrics.last_error = error
        self.metrics.status = "uncertain"
        self._refresh_queue_depth()

    def _mark_failed(self, job_id: int, error: str) -> None:
        if self.store is None:
            return
        self.store.mark_failed(job_id, error)
        self.metrics.failed += 1
        self.metrics.last_error = error
        self.metrics.status = "failed"
        self._refresh_queue_depth()

    @staticmethod
    async def _wait(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
