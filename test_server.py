import io
import os
import sqlite3
import tempfile
import unittest
import json
import re
import threading
import urllib.error
import urllib.request
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


class ListingSerializationTests(unittest.TestCase):
    def test_real_listing_never_uses_sample_photo_and_exposes_creation_time(self):
        row = {
            "id": "RR-real", "title": "Test room", "type": "Private room",
            "owner_id": "OWN-test", "rent": 10000, "deposit": 20000,
            "area": "Dharampeth", "furnishing": "Semi furnished",
            "parking": 0, "electricity_included": 0,
            "available_from": "2026-11-01", "photo": "https://images.unsplash.com/demo.jpg",
            "summary": "Test listing", "amenities": "[]", "is_sample": 0,
            "status": "active", "created_at": "2026-10-17 10:00:00",
        }
        serialized = server.listing_json(row)
        self.assertIsNone(serialized["photo"])
        self.assertEqual(serialized["createdAt"], "2026-10-17 10:00:00")
        self.assertEqual(serialized["maintenanceMode"], "unknown")
        self.assertIsNone(serialized["estimatedMonthlyCost"])

    def test_sample_listing_keeps_its_explicitly_sample_image(self):
        row = {
            "id": "RR-sample", "title": "Test sample", "type": "Private room",
            "owner_id": "OWN-sample", "rent": 10000, "deposit": 20000,
            "area": "Dharampeth", "furnishing": "Semi furnished",
            "parking": 0, "electricity_included": 0,
            "available_from": "2026-11-01", "photo": "https://images.unsplash.com/demo.jpg",
            "summary": "Sample listing", "amenities": "[]", "is_sample": 1,
            "status": "active", "created_at": "2026-10-17 10:00:00",
        }
        serialized = server.listing_json(row)
        self.assertEqual(serialized["photo"], "https://images.unsplash.com/demo.jpg")
        self.assertTrue(serialized["isSample"])


class SecurityHeaderTests(unittest.TestCase):
    def test_production_configuration_gate_requires_shared_services_and_tls(self):
        with patch.object(server,"IS_POSTGRES",False), patch.dict(os.environ,{"APP_ENV":"production","DATABASE_URL":"","REDIS_URL":"","SMTP_HOST":"","SMTP_FROM":"","ROOMROUTE_PUBLIC_URL":"","ROOMROUTE_ALLOWED_HOSTS":""},clear=False):
            with self.assertRaises(SystemExit): server.validate_production_config()
        values={"APP_ENV":"production","DATABASE_URL":"postgresql://db.example/roomroute","REDIS_URL":"rediss://redis.example/0","SMTP_HOST":"smtp.example","SMTP_PORT":"587","SMTP_STARTTLS":"1","SMTP_FROM":"RoomRoute <no-reply@example.test>","ROOMROUTE_PUBLIC_URL":"https://roomroute.example","ROOMROUTE_ALLOWED_HOSTS":"roomroute.example","ROOMROUTE_DB_POOL_SIZE":"20","ROOMROUTE_TRUST_PROXY_CIDRS":""}
        with patch.object(server,"IS_POSTGRES",True), patch.dict(os.environ,values,clear=False):
            server.validate_production_config()

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
        handler.headers = {"Origin": "http://127.0.0.1:8765", "Host": "127.0.0.1:8765"}
        self.assertTrue(server.Handler.check_origin(handler))
        handler.headers["Origin"] = "javascript://roomroute.example"
        self.assertFalse(server.Handler.check_origin(handler))
        handler.headers["Origin"] = "https://attacker.example"
        self.assertFalse(server.Handler.check_origin(handler))

    def test_host_header_cannot_define_its_own_allowlist(self):
        handler = object.__new__(server.Handler)
        handler.headers = {"Origin": "https://attacker.example", "Host": "attacker.example"}
        with patch.dict(os.environ, {"APP_ENV": "development", "ROOMROUTE_PORT": "8765"}):
            self.assertFalse(server.Handler.trusted_host(handler))
            self.assertFalse(server.Handler.check_origin(handler))
        with patch.dict(os.environ, {"APP_ENV": "production", "ROOMROUTE_ALLOWED_HOSTS": "roomroute.example"}):
            handler.headers = {"Origin": "https://roomroute.example", "Host": "roomroute.example"}
            self.assertTrue(server.Handler.trusted_host(handler))
            self.assertTrue(server.Handler.check_origin(handler))

    def test_forwarded_ip_is_trusted_only_from_configured_proxy_networks(self):
        handler=object.__new__(server.Handler)
        handler.client_address=("10.0.1.5",443)
        handler.headers={"X-Forwarded-For":"198.51.100.77, 10.0.2.9"}
        with patch.dict(os.environ,{"ROOMROUTE_TRUST_PROXY_CIDRS":"10.0.0.0/8"}):
            self.assertEqual(server.Handler.client_ip(handler),"198.51.100.77")
        handler.client_address=("198.51.100.8",443)
        with patch.dict(os.environ,{"ROOMROUTE_TRUST_PROXY_CIDRS":"10.0.0.0/8"}):
            self.assertEqual(server.Handler.client_ip(handler),"198.51.100.8")


class ServiceFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.old_db=server.DB
        server.DB=Path(self.tempdir.name)/"service-flow.sqlite3"
        server.init_db()
        try:
            self.http=server.BoundedThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        except OSError as error:
            if getattr(error,"winerror",None)==10013: self.skipTest("Sandbox does not permit local test sockets")
            raise
        self.port=self.http.server_address[1]
        self.base=f"http://127.0.0.1:{self.port}"
        self.env=patch.dict(os.environ,{"APP_ENV":"development","ROOMROUTE_PORT":str(self.port),"ROOMROUTE_PUBLIC_URL":self.base},clear=False)
        self.env.start()
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(timeout=2)
        self.env.stop(); server.DB=self.old_db; self.tempdir.cleanup()

    def call(self,path,method="GET",data=None,cookies=None,csrf=None):
        headers={"Origin":self.base}
        if data is not None: headers["Content-Type"]="application/json"
        if csrf: headers["X-CSRF-Token"]=csrf
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies)) if cookies is not None else urllib.request.build_opener()
        try:
            with opener.open(request,timeout=4) as response:
                return response.status,json.loads(response.read()) if response.status!=204 else {}
        except urllib.error.HTTPError as error:
            return error.code,json.loads(error.read())
        except urllib.error.URLError as error:
            if getattr(error.reason,"winerror",None)==10013: self.skipTest("Sandbox does not permit local test sockets")
            raise

    def create_verified_account(self,email,role):
        status,result=self.call("/api/auth/register","POST",{"name":"Test User","email":email,"password":"a-strong-test-password","role":role})
        self.assertEqual(status,201,result)
        duplicate_status,duplicate=self.call("/api/auth/register","POST",{"name":"Test User","email":email,"password":"a-strong-test-password","role":role})
        self.assertEqual((duplicate_status,duplicate),(status,result))
        with server.db_session() as db:
            body=db.execute("SELECT body FROM email_outbox WHERE recipient=? ORDER BY id DESC LIMIT 1",(email,)).fetchone()["body"]
        token=re.search(r"[#]verify=([^\s]+)",body).group(1)
        status,blocked=self.call("/api/auth/login","POST",{"email":email,"password":"a-strong-test-password"})
        self.assertEqual(status,401,blocked)
        status,result=self.call("/api/auth/verify","POST",{"token":token})
        self.assertEqual(status,200,result)
        self.assertEqual(self.call("/api/auth/verify","POST",{"token":token})[0],400)
        jar=__import__("http.cookiejar").cookiejar.CookieJar()
        status,result=self.call("/api/auth/login","POST",{"email":email,"password":"a-strong-test-password"},jar)
        self.assertEqual(status,200,result)
        self.assertTrue(result["user"]["isVerified"])
        return jar,result["csrfToken"],result["user"]

    def test_pages_are_served_with_security_headers_and_private_files_are_denied(self):
        for path in ("/", "/how-it-works.html", "/safety.html", "/owners.html", "/saved.html", "/pages.css", "/saved.js", "/nav.js"):
            request=urllib.request.Request(self.base+path,headers={"Origin":self.base})
            try:
                response=urllib.request.urlopen(request,timeout=4)
            except urllib.error.URLError as error:
                if getattr(error.reason,"winerror",None)==10013: self.skipTest("Sandbox does not permit local test sockets")
                raise
            with response:
                self.assertEqual(response.status,200,path)
                self.assertEqual(response.headers.get("X-Content-Type-Options"),"nosniff")
                self.assertEqual(response.headers.get("X-Frame-Options"),"DENY")
                self.assertIn("object-src 'none'",response.headers.get("Content-Security-Policy",""))
                self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
        for path in ("/.env", "/.git/config", "/server.py", "/README.md", "/roomroute.sqlite3"):
            self.assertEqual(self.call(path)[0],404,path)

    def test_admin_and_owner_routes_require_their_roles(self):
        self.assertEqual(self.call("/api/moderation/listings")[0],401)
        self.assertEqual(self.call("/api/moderation/reports")[0],401)
        self.assertEqual(self.call("/api/owner/listings")[0],401)
        cookies,_,_=self.create_verified_account("student-scope@example.test","student")
        self.assertEqual(self.call("/api/moderation/listings",cookies=cookies)[0],403)
        self.assertEqual(self.call("/api/moderation/reports",cookies=cookies)[0],403)
        self.assertEqual(self.call("/api/owner/listings",cookies=cookies)[0],403)

    def test_listing_api_filters_and_bounds_pages(self):
        server.seed_sample_data()
        status,first=self.call("/api/listings?limit=20&offset=0&sort=rent-low")
        self.assertEqual(status,200)
        self.assertEqual(len(first["listings"]),20)
        self.assertEqual(first["total"],50)
        self.assertTrue(first["hasMore"])
        status,last=self.call("/api/listings?limit=1000&offset=49")
        self.assertEqual(status,200)
        self.assertEqual(len(last["listings"]),1)
        self.assertEqual(last["limit"],server.LISTING_PAGE_MAX)
        status,filtered=self.call("/api/listings?area=Dharampeth&budget=10000&parking=yes")
        self.assertEqual(status,200)
        self.assertTrue(all(row["area"]=="Dharampeth" and row["rent"]<=10000 and row["parking"] for row in filtered["listings"]))

    def test_login_throttle_runs_before_password_hash(self):
        for _ in range(8):
            self.assertEqual(self.call("/api/auth/login","POST",{"email":"missing@example.test","password":"incorrect-password"})[0],401)
        self.assertEqual(self.call("/api/auth/login","POST",{"email":"missing@example.test","password":"incorrect-password"})[0],429)

    def test_verification_listing_approval_inquiry_report_and_privacy(self):
        owner_cookies,owner_csrf,owner=self.create_verified_account("owner@example.test","owner")
        listing_payload={"title":"Bright room near campus","type":"Private room","area":"Dharampeth","rent":11000,"deposit":22000,"rentBasis":"whole_property","maintenanceMode":"extra","maintenanceAmount":750,"ownerAuthorized":True,"furnishing":"Semi furnished","availableFrom":"2026-11-01","parking":True,"electricityIncluded":False,"summary":"A genuine test listing."}
        unauthorized={**listing_payload,"ownerAuthorized":False}
        self.assertEqual(self.call("/api/listings","POST",unauthorized,owner_cookies,owner_csrf)[0],400)
        invalid_cost={**listing_payload,"maintenanceAmount":0}
        self.assertEqual(self.call("/api/listings","POST",invalid_cost,owner_cookies,owner_csrf)[0],400)
        status,created=self.call("/api/listings","POST",listing_payload,owner_cookies,owner_csrf)
        self.assertEqual(status,201,created)
        self.assertEqual(created["status"],"pending")
        self.assertEqual(self.call("/api/listings")[1]["listings"],[])

        moderator_password="moderator-test-password"
        with server.db_session() as db:
            db.execute("INSERT INTO accounts(id,email,name,role,password_hash,is_verified) VALUES(?,?,?,?,?,1)",("MOD-test","mod@example.test","Moderator","moderator",server.PASSWORD_HASHER.hash(moderator_password)))
        mod_cookies=__import__("http.cookiejar").cookiejar.CookieJar()
        status,moderator=self.call("/api/auth/login","POST",{"email":"mod@example.test","password":moderator_password},mod_cookies)
        self.assertEqual(status,200,moderator)
        status,approved=self.call(f"/api/moderation/listings/{created['id']}","POST",{"action":"approve","note":"Checked in test."},mod_cookies,moderator["csrfToken"])
        self.assertEqual(status,200,approved)
        public_listings=self.call("/api/listings")[1]["listings"]
        self.assertEqual(len(public_listings),1)
        self.assertIsNone(public_listings[0]["photo"])
        self.assertTrue(public_listings[0]["createdAt"])
        self.assertEqual(public_listings[0]["maintenanceMode"],"extra")
        self.assertEqual(public_listings[0]["maintenanceAmount"],750)
        self.assertEqual(public_listings[0]["estimatedMonthlyCost"],11750)

        renter_cookies,renter_csrf,renter=self.create_verified_account("renter@example.test","student")
        status,inquiry=self.call("/api/inquiries","POST",{"listingId":created["id"],"message":"Can I visit this room?"},renter_cookies,renter_csrf)
        self.assertEqual(status,201,inquiry)
        status,owner_inbox=self.call("/api/inquiries",cookies=owner_cookies)
        self.assertEqual(status,200)
        self.assertEqual(owner_inbox[0]["id"],inquiry["id"])
        status,reported=self.call(f"/api/listings/{created['id']}/report","POST",{"reason":"Misleading information","details":"Test report."},renter_cookies,renter_csrf)
        self.assertEqual(status,201,reported)
        reports=self.call("/api/moderation/reports",cookies=mod_cookies)[1]
        self.assertEqual(len(reports),1)
        self.assertEqual(self.call(f"/api/moderation/reports/{reports[0]['id']}","POST",{"status":"dismissed"},mod_cookies,moderator["csrfToken"])[0],200)

        status,closed=self.call(f"/api/owner/listings/{created['id']}/availability","POST",{"action":"close"},owner_cookies,owner_csrf)
        self.assertEqual(status,200,closed)
        self.assertEqual(self.call("/api/listings")[1]["listings"],[])
        self.assertEqual(self.call("/api/owner/listings",cookies=owner_cookies)[1][0]["status"],"paused")
        status,relisted=self.call(f"/api/owner/listings/{created['id']}/availability","POST",{"action":"relist"},owner_cookies,owner_csrf)
        self.assertEqual(status,200,relisted)
        self.assertEqual(self.call("/api/owner/listings",cookies=owner_cookies)[1][0]["status"],"pending")

        status,export=self.call("/api/account/export",cookies=renter_cookies)
        self.assertEqual(status,200)
        self.assertEqual(export["account"]["email"],renter["email"])
        self.call("/api/auth/password-reset/request","POST",{"email":renter["email"]})
        with server.db_session() as db:
            reset_body=db.execute("SELECT body FROM email_outbox WHERE recipient=? ORDER BY id DESC LIMIT 1",(renter["email"],)).fetchone()["body"]
        reset_token=re.search(r"[#]reset=([^\s]+)",reset_body).group(1)
        new_password="a-new-strong-password"
        self.assertEqual(self.call("/api/auth/password-reset/complete","POST",{"token":reset_token,"password":new_password})[0],200)
        self.assertEqual(self.call("/api/auth/password-reset/complete","POST",{"token":reset_token,"password":new_password})[0],400)
        self.assertEqual(self.call("/api/auth/login","POST",{"email":renter["email"],"password":"a-strong-test-password"})[0],401)
        renter_cookies=__import__("http.cookiejar").cookiejar.CookieJar()
        status,new_session=self.call("/api/auth/login","POST",{"email":renter["email"],"password":new_password},renter_cookies)
        self.assertEqual(status,200,new_session)
        status,deleted=self.call("/api/account/delete","POST",{"password":new_password},renter_cookies,new_session["csrfToken"])
        self.assertEqual(status,200,deleted)
        with server.db_session() as db:
            self.assertIsNone(db.execute("SELECT id FROM accounts WHERE id=?",(renter["id"],)).fetchone())
            self.assertIsNone(db.execute("SELECT id FROM users WHERE id=?",(renter["id"],)).fetchone())


class PostgreSQLBackendTests(unittest.TestCase):
    def test_postgresql_schema_transactions_rows_and_redis_limits(self):
        url=os.environ.get("TEST_POSTGRES_URL")
        if not url: self.skipTest("TEST_POSTGRES_URL is not configured")
        old_url,old_flag,old_pool=server.DATABASE_URL,server.IS_POSTGRES,server._pg_pool
        server.DATABASE_URL=url; server.IS_POSTGRES=True; server._pg_pool=None
        suffix=__import__("secrets").token_hex(6)
        owner_id=f"TEST-OWN-{suffix}"; user_id=f"TEST-USR-{suffix}"; listing_id=f"TEST-RR-{suffix}"
        try:
            server.init_db()
            with server.db_session() as db:
                db.execute("INSERT INTO owners(id,name,email,is_sample) VALUES(?,?,?,0)",(owner_id,"DB Test Owner",f"owner-{suffix}@example.test"))
                db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES(?,?,?,?,?,?,0)",(user_id,"DB Test Renter",f"renter-{suffix}@example.test","student","student",10000))
                db.execute("INSERT INTO accounts(id,email,name,role,password_hash,is_verified) VALUES(?,?,?,?,?,1)",(owner_id,f"owner-{suffix}@example.test","DB Test Owner","owner","hash"))
                db.execute("INSERT INTO listings(id,owner_id,title,type,rent,deposit,area,furnishing,parking,electricity_included,available_from,photo,summary,amenities,is_sample) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",(listing_id,owner_id,"Postgres test listing","Private room",10000,20000,"Dharampeth","Semi furnished",0,0,"2026-11-01","https://example.test/room.jpg","Postgres test","[]"))
                listing=db.execute("SELECT id,status FROM listings WHERE id=?",(listing_id,)).fetchone()
                self.assertEqual(listing[0],listing_id)
                self.assertEqual(listing["status"],"pending")
                inquiry_id=db.execute("INSERT INTO inquiries(listing_id,student_id,message) VALUES(?,?,?) RETURNING id",(listing_id,user_id,"Test inquiry message")).fetchone()[0]
                self.assertGreater(inquiry_id,0)
                server.queue_email(db,f"owner-{suffix}@example.test","Test outbox","Delivery test")
            handler=object.__new__(server.Handler); handler.client_address=("127.0.0.1",99); handler.headers={}
            redis_url=os.environ.get("TEST_REDIS_URL")
            if redis_url:
                with patch.dict(os.environ,{"REDIS_URL":redis_url,"APP_ENV":"production"}):
                    action=f"integration-{suffix}"
                    with server.db_session() as db:
                        self.assertTrue(server.Handler.allow_write(handler,db,action,1,60))
                        self.assertFalse(server.Handler.allow_write(handler,db,action,1,60))
        finally:
            with patch.dict(os.environ,{"APP_ENV":"development","SMTP_HOST":""}):
                try:
                    if server._pg_pool is not None:
                        with server.db_session() as db:
                            db.execute("DELETE FROM inquiries WHERE listing_id=?",(listing_id,))
                            db.execute("DELETE FROM listings WHERE id=?",(listing_id,))
                            db.execute("DELETE FROM email_outbox WHERE recipient LIKE ?",(f"owner-{suffix}@example.test",))
                            db.execute("DELETE FROM users WHERE id=?",(user_id,))
                            db.execute("DELETE FROM accounts WHERE id=?",(owner_id,))
                            db.execute("DELETE FROM owners WHERE id=?",(owner_id,))
                except Exception:
                    pass
            if server._pg_pool is not None: server._pg_pool.close()
            server.DATABASE_URL,server.IS_POSTGRES,server._pg_pool=old_url,old_flag,old_pool

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

