"""Verify ingress users against Home Assistant, not sidebar visibility."""
from __future__ import annotations

import asyncio
import os
import time

from aiohttp import ClientSession


class AdminAuthorizationUnavailable(RuntimeError):
    pass


class HomeAssistantAdminAuthorizer:
    """Cache only active human administrator IDs for at most 30 seconds."""

    def __init__(self, *, token: str | None = None, ttl: float = 30) -> None:
        self._token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")
        self._ttl = ttl
        self._expires = 0.0
        self._ids: frozenset[str] = frozenset()
        self._lock = asyncio.Lock()

    @staticmethod
    def admin_ids(users: list) -> frozenset[str]:
        return frozenset(
            user["id"] for user in users
            if isinstance(user, dict) and isinstance(user.get("id"), str)
            and user.get("is_active") is True and user.get("system_generated") is False
            and (user.get("is_owner") is True or "system-admin" in user.get("group_ids", []))
        )

    async def _load(self) -> frozenset[str]:
        if not self._token:
            raise AdminAuthorizationUnavailable("Home Assistant authorization unavailable")
        try:
            async with asyncio.timeout(5):
                async with ClientSession() as session:
                    async with session.ws_connect("http://supervisor/core/websocket", max_msg_size=1024 * 1024) as ws:
                        if (await ws.receive_json()).get("type") != "auth_required":
                            raise ValueError("unexpected authentication response")
                        await ws.send_json({"type": "auth", "access_token": self._token})
                        if (await ws.receive_json()).get("type") != "auth_ok":
                            raise ValueError("authentication rejected")
                        await ws.send_json({"id": 1, "type": "config/auth/list"})
                        reply = await ws.receive_json()
                        if reply.get("id") != 1 or reply.get("success") is not True or not isinstance(reply.get("result"), list):
                            raise ValueError("administrator lookup rejected")
                        return self.admin_ids(reply["result"])
        except Exception as exc:
            # Never include websocket messages, user lists, or tokens in errors.
            raise AdminAuthorizationUnavailable("Home Assistant authorization unavailable") from exc

    async def allowed(self, user_id: str) -> bool:
        async with self._lock:
            if time.monotonic() >= self._expires:
                self._ids = frozenset()
                try:
                    self._ids = await self._load()
                except Exception:
                    self._expires = 0.0
                    raise
                self._expires = time.monotonic() + self._ttl
            return user_id in self._ids
