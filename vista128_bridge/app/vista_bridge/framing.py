from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RawFrame:
    data: bytes
    received_at: str
    termination: str

    @classmethod
    def create(cls, data: bytes, termination: str) -> "RawFrame":
        return cls(
            data=data,
            received_at=datetime.now(timezone.utc).isoformat(),
            termination=termination,
        )

    @property
    def ascii(self) -> str:
        return self.data.decode("ascii", errors="replace")

    @property
    def hex(self) -> str:
        return self.data.hex(" ")


class VistaStreamFramer:
    """Frame CR/LF-delimited VISTA records."""

    def __init__(self, max_buffer: int = 8192) -> None:
        self._buffer = bytearray()
        self.max_buffer = max_buffer

    def feed(self, chunk: bytes) -> list[RawFrame]:
        self._buffer.extend(chunk)
        frames: list[RawFrame] = []

        while True:
            newline = self._buffer.find(b"\n")
            if newline < 0:
                break
            record = bytes(self._buffer[:newline])
            del self._buffer[: newline + 1]
            if record.endswith(b"\r"):
                record = record[:-1]
                termination = "crlf"
            else:
                termination = "lf"
            if record:
                frames.append(RawFrame.create(record, termination))

        if len(self._buffer) > self.max_buffer:
            frames.append(RawFrame.create(bytes(self._buffer), "overflow"))
            self._buffer.clear()

        return frames

    def flush_idle(self) -> RawFrame | None:
        if not self._buffer:
            return None
        record = bytes(self._buffer)
        self._buffer.clear()
        return RawFrame.create(record, "idle")
