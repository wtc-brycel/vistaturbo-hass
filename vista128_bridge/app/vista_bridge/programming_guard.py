from __future__ import annotations

from dataclasses import dataclass

from .protocol import validate_packet


@dataclass(frozen=True)
class GuardUpdate:
    partition: int
    next_history: str
    blocked: bool


class InstallerProgrammingGuard:
    """Prevent remote keypad entry into VISTA installer programming.

    Entering installer programming disables the Home/Facility Automation
    interface until the panel is exited locally. The bridge therefore treats
    any four numeric digits followed by ``800`` as a hard safety interlock.
    Blocking ``dddd800`` also prevents the Turbo ``dddd8000`` sequence before
    its final digit can ever be sent.

    The guard tracks only the last six numeric keypad strokes per partition.
    Any non-numeric keypad stroke resets the numeric history. No installer or
    user code is stored outside this short in-memory rolling history, and the
    history is reset for every TCP session.
    """

    def __init__(self) -> None:
        self._history: dict[int, str] = {}

    def reset(self) -> None:
        self._history.clear()

    def inspect_frame(self, frame: bytes) -> GuardUpdate | None:
        decoded = self._decode_keypad_frame(frame)
        if decoded is None:
            return None
        partition, strokes = decoded
        history = self._history.get(partition, "")
        next_history = history

        for stroke in strokes:
            if stroke.isdigit():
                candidate = f"{next_history}{stroke}"
                if len(candidate) >= 7 and candidate[-3:] == "800":
                    return GuardUpdate(
                        partition=partition,
                        next_history=next_history,
                        blocked=True,
                    )
                next_history = candidate[-6:]
            else:
                next_history = ""

        return GuardUpdate(
            partition=partition,
            next_history=next_history,
            blocked=False,
        )

    def commit(self, update: GuardUpdate | None) -> None:
        if update is None or update.blocked:
            return
        if update.next_history:
            self._history[update.partition] = update.next_history
        else:
            self._history.pop(update.partition, None)

    @staticmethod
    def _decode_keypad_frame(frame: bytes) -> tuple[int, str] | None:
        if not isinstance(frame, bytes):
            return None
        packet = frame[:-2] if frame.endswith(b"\r\n") else frame
        if len(packet) < 9 or packet[2:4] != b"KS":
            return None
        if not validate_packet(packet).valid:
            return None

        payload = packet[4:-4]
        if len(payload) < 2:
            return None
        try:
            partition = int(chr(payload[0]))
            encoded = payload[1:].decode("ascii")
        except (ValueError, UnicodeDecodeError):
            return None
        if partition < 1 or partition > 8:
            return None

        strokes = []
        for value in encoded:
            if value.isdigit():
                strokes.append(value)
            elif value == "A":
                strokes.append("*")
            elif value == "B":
                strokes.append("#")
            else:
                # Panic/function encodings are non-numeric from the guard's
                # perspective and must break a prospective installer sequence.
                strokes.append("?")
        return partition, "".join(strokes)
