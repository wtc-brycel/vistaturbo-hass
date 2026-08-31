from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import json

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_SCHEMA


class VistaTurboApiError(Exception):
    """Base native API error."""


class VistaTurboCannotConnect(VistaTurboApiError):
    """The app API cannot be reached."""


class VistaTurboAuthError(VistaTurboApiError):
    """The app API rejected the machine credential."""


class VistaTurboProtocolError(VistaTurboApiError):
    """The app returned an unsupported or malformed API payload."""


class VistaTurboCommandError(VistaTurboApiError):
    """The app rejected a semantic control request."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


def _validate_snapshot(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != API_SCHEMA:
        raise VistaTurboProtocolError("unsupported Vista Turbo native API schema")
    for key in ("panel", "partitions", "zones", "keypads"):
        if key not in payload:
            raise VistaTurboProtocolError(f"native API snapshot missing {key}")
    return payload


def _validate_panel_event(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != API_SCHEMA:
        raise VistaTurboProtocolError("unsupported Vista Turbo event schema")
    sequence = payload.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise VistaTurboProtocolError("Vista Turbo event has an invalid sequence")
    if not isinstance(payload.get("event_type"), str) or not payload["event_type"]:
        raise VistaTurboProtocolError("Vista Turbo event has no event type")
    return payload


def _validate_event_gap(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != API_SCHEMA:
        raise VistaTurboProtocolError("unsupported Vista Turbo event-gap schema")
    if payload.get("reason") not in {"sequence_reset", "replay_window_exceeded"}:
        raise VistaTurboProtocolError("Vista Turbo event gap has an invalid reason")
    reset_to = payload.get("reset_to")
    if isinstance(reset_to, bool) or not isinstance(reset_to, int) or reset_to < 0:
        raise VistaTurboProtocolError("Vista Turbo event gap has an invalid reset point")
    return payload


class VistaTurboApiClient:
    def __init__(self, session: ClientSession, host: str, port: int, token: str) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {token}"}

    async def async_get_snapshot(self) -> dict:
        try:
            async with self._session.get(
                f"{self._base_url}/v1/snapshot",
                headers=self._headers,
                timeout=ClientTimeout(total=10),
            ) as response:
                if response.status == 401:
                    raise VistaTurboAuthError
                response.raise_for_status()
                return _validate_snapshot(await response.json())
        except (VistaTurboAuthError, VistaTurboProtocolError):
            raise
        except (ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise VistaTurboCannotConnect from err

    async def async_alarm_command(
        self,
        *,
        partition: int,
        action: str,
        code: str,
        user_id: str,
        user_name: str,
        context_id: str,
    ) -> dict:
        payload = {
            "partition": partition,
            "action": action,
            "code": code,
            "actor": {"user_id": user_id, "name": user_name},
            "context_id": context_id,
        }
        try:
            async with self._session.post(
                f"{self._base_url}/v1/control/alarm",
                headers=self._headers,
                json=payload,
                timeout=ClientTimeout(total=10),
            ) as response:
                if response.status == 401:
                    raise VistaTurboAuthError
                response_payload = await response.json()
                if response.status != 202:
                    status = (
                        str(response_payload.get("error", "command_rejected"))
                        if isinstance(response_payload, dict)
                        else "command_rejected"
                    )
                    raise VistaTurboCommandError(status)
                if not isinstance(response_payload, dict):
                    raise VistaTurboProtocolError("invalid alarm control response")
                return response_payload
        except (VistaTurboAuthError, VistaTurboCommandError, VistaTurboProtocolError):
            raise
        except (ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise VistaTurboCannotConnect from err

    async def async_snapshots(self) -> AsyncIterator[dict]:
        timeout = ClientTimeout(total=None, connect=10, sock_read=60)
        try:
            async with self._session.get(
                f"{self._base_url}/v1/stream",
                headers=self._headers,
                timeout=timeout,
            ) as response:
                if response.status == 401:
                    raise VistaTurboAuthError
                response.raise_for_status()
                data_lines: list[str] = []
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8").rstrip("\r\n")
                    if not line:
                        if data_lines:
                            yield _validate_snapshot(json.loads("\n".join(data_lines)))
                            data_lines.clear()
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
        except (
            VistaTurboAuthError,
            VistaTurboProtocolError,
            asyncio.CancelledError,
        ):
            raise
        except (ClientError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as err:
            raise VistaTurboCannotConnect from err

    async def async_events(self, after_sequence: int = 0) -> AsyncIterator[dict]:
        """Yield ordered panel events and explicit replay-gap notifications."""
        timeout = ClientTimeout(total=None, connect=10, sock_read=60)
        headers = dict(self._headers)
        if after_sequence > 0:
            headers["Last-Event-ID"] = str(after_sequence)
        try:
            async with self._session.get(
                f"{self._base_url}/v1/events",
                headers=headers,
                timeout=timeout,
            ) as response:
                if response.status == 401:
                    raise VistaTurboAuthError
                response.raise_for_status()
                event_name = ""
                data_lines: list[str] = []
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8").rstrip("\r\n")
                    if not line:
                        if data_lines:
                            payload = json.loads("\n".join(data_lines))
                            if event_name == "panel_event":
                                yield {
                                    "kind": "event",
                                    "data": _validate_panel_event(payload),
                                }
                            elif event_name == "gap":
                                yield {
                                    "kind": "gap",
                                    "data": _validate_event_gap(payload),
                                }
                            data_lines.clear()
                            event_name = ""
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
        except (
            VistaTurboAuthError,
            VistaTurboProtocolError,
            asyncio.CancelledError,
        ):
            raise
        except (ClientError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as err:
            raise VistaTurboCannotConnect from err
