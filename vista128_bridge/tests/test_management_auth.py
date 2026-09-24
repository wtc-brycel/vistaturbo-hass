from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vista_bridge.management_auth import IngressIdentity, ManagementAuthorizer
from vista_bridge.management_store import ManagementStore


def _store(path: Path) -> ManagementStore:
    db_path = str(path / "events.sqlite3")
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    return ManagementStore(db_path)


class ManagementAuthTests(unittest.TestCase):
    def test_ingress_identity_is_mandatory(self):
        with self.assertRaises(PermissionError):
            ManagementAuthorizer.identity_from_headers({})
        identity = ManagementAuthorizer.identity_from_headers(
            {"X-Remote-User-Id": "ha-1", "X-Remote-User-Name": "Administrator"}
        )
        self.assertEqual(
            identity,
            IngressIdentity(user_id="ha-1", user_name="Administrator"),
        )

    def test_elevation_is_bound_to_authenticated_actor(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = ManagementAuthorizer(_store(Path(directory)), ttl_minutes=20)
            first = IngressIdentity("ha-1", "First")
            second = IngressIdentity("ha-2", "Second")
            token = auth.setup(first, "correct horse battery staple")
            self.assertTrue(auth.elevated(first, token))
            self.assertFalse(auth.elevated(second, token))
            auth.lock(first, token)
            self.assertFalse(auth.elevated(first, token))

    def test_first_run_setup_is_single_use(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = ManagementAuthorizer(_store(Path(directory)))
            identity = IngressIdentity("ha-1", "Administrator")
            token = auth.setup(identity, "correct horse battery staple")
            self.assertTrue(auth.elevated(identity, token))
            self.assertTrue(auth.unlock_configured())
            with self.assertRaisesRegex(RuntimeError, "already configured"):
                auth.setup(identity, "another correct horse battery staple")

    def test_wrong_unlock_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = ManagementAuthorizer(_store(Path(directory)))
            identity = IngressIdentity("ha-1", "Administrator")
            auth.setup(identity, "correct horse battery staple")
            with self.assertRaisesRegex(PermissionError, "unlock failed"):
                auth.unlock(identity, "definitely wrong")


if __name__ == "__main__":
    unittest.main()
