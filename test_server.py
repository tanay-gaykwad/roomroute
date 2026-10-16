import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class RequestBodyTests(unittest.TestCase):
    def request(self, raw, content_type="application/json", length=None, transfer_encoding=None):
        headers = {"Content-Type": content_type, "Content-Length": str(len(raw)) if length is None else str(length)}
        if transfer_encoding:
            headers["Transfer-Encoding"] = transfer_encoding
        return type("Request", (), {"headers": headers, "rfile": io.BytesIO(raw)})()

    def test_accepts_json_object(self):
        self.assertEqual(server.Handler.body(self.request(b'{"ok":true}')), {"ok": True})

    def test_rejects_json_array(self):
        with self.assertRaises(ValueError):
            server.Handler.body(self.request(b"[]"))

    def test_rejects_oversized_and_chunked_bodies(self):
        with self.assertRaises(ValueError):
            server.Handler.body(self.request(b"{}", length=server.MAX_REQUEST_BYTES + 1))
        with self.assertRaises(ValueError):
            server.Handler.body(self.request(b"{}", transfer_encoding="chunked"))

    def test_rejects_non_json_content_type(self):
        with self.assertRaises(ValueError):
            server.Handler.body(self.request(b"{}", content_type="text/plain"))


class PreviewDataSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.old_db = server.DB
        server.DB = Path(self.tempdir.name) / "roomroute-test.sqlite3"
        server.init_db()

    def tearDown(self):
        server.DB = self.old_db
        self.tempdir.cleanup()

    def test_seed_is_idempotent_and_removable(self):
        self.assertTrue(server.seed_sample_data())
        self.assertFalse(server.seed_sample_data())
        with server.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM listings WHERE is_sample=1").fetchone()[0], 50)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users WHERE is_sample=1").fetchone()[0], 200)
        server.remove_sample_data()
        with server.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM listings").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_seed_refuses_real_records_without_relabeling_or_deleting_them(self):
        with server.db_session() as db:
            db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES('real-user','Real User','real@example.test','student','student',10000,0)")
        with self.assertRaises(RuntimeError):
            server.seed_sample_data()
        with server.db_session() as db:
            row = db.execute("SELECT is_sample FROM users WHERE id='real-user'").fetchone()
            self.assertEqual(row["is_sample"], 0)
        server.remove_sample_data()
        with server.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users WHERE id='real-user'").fetchone()[0], 1)

    def test_seed_refuses_orphaned_account_rows(self):
        with server.db_session() as db:
            db.execute("INSERT INTO accounts(id,email,name,role,password_hash) VALUES('orphan','orphan@example.test','Orphan','student','hash')")
        with self.assertRaises(RuntimeError):
            server.seed_sample_data()
        with server.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM accounts WHERE id='orphan'").fetchone()[0], 1)


class SecurityHeaderTests(unittest.TestCase):
    def test_forwarded_proto_does_not_control_secure_cookie(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"X-Forwarded-Proto": "https"}
        handler.response_cookie = None
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE sessions(token_hash TEXT,account_id TEXT,csrf_token TEXT,expires_at TEXT)")
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            server.Handler.create_session(handler, db, "account")
        self.assertNotIn("; Secure", handler.response_cookie)
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            server.Handler.create_session(handler, db, "account")
            self.assertEqual(server.Handler.cookie_name(), "__Host-roomroute_session")
            self.assertTrue(handler.response_cookie.startswith("__Host-roomroute_session="))
            self.assertIn("; Secure", handler.response_cookie)
        db.close()

    def test_origin_requires_matching_host_and_valid_scheme(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"Origin": "https://roomroute.example", "Host": "roomroute.example"}
        self.assertTrue(server.Handler.check_origin(handler))
        handler.headers["Origin"] = "javascript://roomroute.example"
        self.assertFalse(server.Handler.check_origin(handler))
        handler.headers["Origin"] = "https://attacker.example"
        self.assertFalse(server.Handler.check_origin(handler))

    def test_write_rate_limit_is_enforced_per_action_and_ip(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE request_limits(id INTEGER PRIMARY KEY, action TEXT, ip_address TEXT, occurred_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        handler = object.__new__(server.Handler)
        handler.client_address = ("127.0.0.1", 1234)
        self.assertTrue(server.Handler.allow_write(handler, db, "test", 2, 3600))
        self.assertTrue(server.Handler.allow_write(handler, db, "test", 2, 3600))
        self.assertFalse(server.Handler.allow_write(handler, db, "test", 2, 3600))
        self.assertTrue(server.Handler.allow_write(handler, db, "other", 2, 3600))
        db.close()


if __name__ == "__main__":
    unittest.main()

