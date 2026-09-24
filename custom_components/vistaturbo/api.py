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
    """The app returned an unsupported or malformed API snapshot."""


def _validate_snapshot(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != API_SCHEMA:
        raise VistaTurboProtocolError("unsupported Vista Turbo native API schema")
    for key in ("panel", "partitions", "zones", "keypads"):
        if key not in payload:
            raise VistaTurboProtocolError(f"native API snapshot missing {key}")
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
