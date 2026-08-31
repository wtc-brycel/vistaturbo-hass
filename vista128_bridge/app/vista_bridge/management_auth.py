from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import threading

from .management_store import ManagementStore


@dataclass(frozen=True)
class IngressIdentity:
    user_id: str
    user_name: str


@dataclass
class _Session:
    actor_id: str
    expires_at: datetime


class ManagementAuthorizer:
    """HA-ingress identity plus short-lived Vista administrator elevation."""

    def __init__(
        self,
        store: ManagementStore,
        *,
        ttl_minutes: int = 20,
    ) -> None:
        self.store = store
        self.ttl = timedelta(minutes=max(1, min(120, int(ttl_minutes))))
        self._sessions: dict[str, _Session] = {}
        self._failures: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def identity_from_headers(headers) -> IngressIdentity:
        user_id = str(headers.get("X-Remote-User-Id", "")).strip()
        if not user_id:
            raise PermissionError("Home Assistant ingress identity is required")
        user_name = str(headers.get("X-Remote-User-Name", "")).strip()
        return IngressIdentity(user_id=user_id[:128], user_name=user_name[:128])

    def unlock_configured(self) -> bool:
        return self.store.admin_unlock_configured()

    def setup(self, identity: IngressIdentity, secret: str) -> str:
        # ThreadingHTTPServer can service simultaneous first-run requests. Keep
        # setup single-writer so a second request cannot replace the password
        # after the first request has configured it.
        with self._lock:
            if self.unlock_configured():
                raise RuntimeError("administrator unlock is already configured")
            self.store.configure_admin_unlock(secret)
        return self._issue(identity.user_id)

    def unlock(self, identity: IngressIdentity, secret: str) -> str:
        now = datetime.now(timezone.utc)
        with self._lock:
            recent = [
                timestamp
                for timestamp in self._failures.get(identity.user_id, [])
                if now - timestamp < timedelta(minutes=5)
            ]
            self._failures[identity.user_id] = recent
            if len(recent) >= 5:
                raise PermissionError("too many failed administrator unlock attempts")
        if not self.store.verify_admin_unlock(secret):
            with self._lock:
                self._failures.setdefault(identity.user_id, []).append(now)
            raise PermissionError("administrator unlock failed")
        with self._lock:
            self._failures.pop(identity.user_id, None)
        return self._issue(identity.user_id)

    def _issue(self, actor_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(now)
            self._sessions[token] = _Session(
                actor_id=actor_id,
                expires_at=now + self.ttl,
            )
        return token

    def elevated(self, identity: IngressIdentity, token: str | None) -> bool:
        if not token:
            return False
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(now)
            session = self._sessions.get(token)
            return bool(
                session
                and session.actor_id == identity.user_id
                and session.expires_at > now
            )

    def lock(self, identity: IngressIdentity, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            session = self._sessions.get(token)
            if session and session.actor_id == identity.user_id:
                self._sessions.pop(token, None)

    def _prune_locked(self, now: datetime) -> None:
        expired = [
            token
            for token, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)
