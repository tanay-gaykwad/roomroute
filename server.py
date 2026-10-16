"""Local RoomRoute preview server. Uses only Python's standard library and SQLite."""
from __future__ import annotations

import json
import argparse
import os
import secrets
import sqlite3
import traceback
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("ROOMROUTE_DB_PATH", str(ROOT / "roomroute.sqlite3"))).resolve()
AREAS = ["Dharampeth", "Bajaj Nagar", "Laxmi Nagar", "Pratap Nagar", "Manish Nagar", "Trimurti Nagar", "Ramdaspeth", "Civil Lines", "Sadar", "Wardha Road"]
NAMES = ["Aarav Deshmukh", "Meera Kulkarni", "Rohan Patil", "Ananya Joshi", "Siddharth Shah", "Isha Nair", "Kabir Rao", "Neha Gokhale", "Aditya Sinha", "Tanvi Bapat", "Vihaan More", "Sana Khan", "Arjun Reddy", "Mira Chavan", "Dev Malhotra", "Riya Korde", "Ishaan Kulkarni", "Nisha Jadhav", "Omkar Desai", "Tara Menon", "Kunal Bhosale", "Aditi Puri", "Reyansh Pawar", "Zoya Merchant", "Atharv Kale", "Diya Shah", "Neil Wankhede", "Pooja Thakur", "Yash Mehta", "Saanvi Gupte", "Parth Agrawal", "Kavya Pillai", "Rudra Dube", "Simran Kaur", "Manav Borkar", "Anvi Rane", "Dhruv Jain", "Leena Naidu", "Ayaan Sheikh", "Sia Vaidya", "Harsh Tiwari", "Mahi Sable", "Nikhil Kamat", "Ira Roy", "Pranav Bhandari", "Esha Soni", "Samar Gawande", "Rhea Dutta", "Aarush Naik", "Tiya Mishra"]
SEEDS = [
    ("Sunlit room in a calm shared home", "Private room", 10500, 21000, "Fully furnished", 1, 1, 4.8, "photo-1522708323590-d24dbb6b0267"),
    ("A bright room, steps from campus", "Private room", 8500, 17000, "Semi furnished", 0, 0, 4.7, "photo-1505693416388-ac5ce068fe85"),
    ("Easy living in a roomy 2 BHK", "2 BHK flat", 22000, 44000, "Fully furnished", 1, 1, 4.9, "photo-1600210492486-724fe5c67fb0"),
    ("Shared space with a friendly vibe", "Shared room", 6000, 12000, "Fully furnished", 1, 0, 4.5, "photo-1600607687939-ce8a6c25118c"),
    ("A little home near the green", "1 BHK flat", 15500, 30000, "Semi furnished", 1, 1, 4.6, "photo-1600566753086-00f18fb6b3ea"),
    ("Quiet private room with a balcony", "Private room", 12000, 24000, "Fully furnished", 0, 1, 4.8, "photo-1600607687920-4e2a09cf159d"),
    ("Your own corner in a shared flat", "Private room", 9000, 18000, "Semi furnished", 1, 0, 4.4, "photo-1600566753190-17f0baa2a6c3"),
    ("Open, airy 2 BHK near the main road", "2 BHK flat", 25000, 50000, "Fully furnished", 1, 1, 4.7, "photo-1616486338812-3dadae4b4ace"),
    ("Comfortable shared room, all set up", "Shared room", 5500, 11000, "Fully furnished", 0, 0, 4.3, "photo-1600585154340-be6161a56a0c"),
    ("A neat 1 BHK for your next chapter", "1 BHK flat", 14500, 29000, "Unfurnished", 1, 1, 4.6, "photo-1600607687644-c7171b42498f"),
]
PASSWORD_HASHER = PasswordHasher()
SESSION_COOKIE = "roomroute_session"
SESSION_DAYS = 7


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


@contextmanager
def db_session():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with db_session() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS owners(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL DEFAULT 'owner', is_sample INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL, occupation TEXT NOT NULL, budget INTEGER NOT NULL, is_sample INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owners(id), title TEXT NOT NULL, type TEXT NOT NULL, rent INTEGER NOT NULL, deposit INTEGER NOT NULL, area TEXT NOT NULL, city TEXT NOT NULL DEFAULT 'Nagpur', furnishing TEXT NOT NULL, parking INTEGER NOT NULL, electricity_included INTEGER NOT NULL, available_from TEXT NOT NULL, photo TEXT NOT NULL, summary TEXT NOT NULL, amenities TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', is_sample INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inquiries(id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id TEXT NOT NULL REFERENCES listings(id), student_id TEXT NOT NULL REFERENCES users(id), message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','student','employee')), password_hash TEXT NOT NULL, is_verified INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS auth_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT NOT NULL, email TEXT NOT NULL, failed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_auth_attempts_lookup ON auth_attempts(ip_address,email,failed_at);
        """)
        # Safe migrations for databases created by the earlier local preview.
        for table in ("owners", "users", "listings"):
            columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            if "is_sample" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
                db.execute(f"UPDATE {table} SET is_sample=1")


def seed_sample_data():
    with db_session() as db:
        if db.execute("SELECT COUNT(*) FROM owners WHERE is_sample=1").fetchone()[0] > 0:
            return False
        if db.execute("SELECT COUNT(*) FROM owners WHERE is_sample=0").fetchone()[0] > 0:
            raise RuntimeError("Sample data can only be loaded into an empty owner inventory; remove sample data first.")
        db.execute("UPDATE owners SET is_sample=1")
        db.execute("UPDATE users SET is_sample=1")
        db.execute("UPDATE listings SET is_sample=1")
        if db.execute("SELECT COUNT(*) FROM owners").fetchone()[0] == 0:
            for i, name in enumerate(NAMES):
                oid = f"OWN-{i+1:03}"
                db.execute("INSERT INTO owners(id,name,email,is_sample) VALUES(?,?,?,1)", (oid, name, f"owner{i+1:03}@example.com"))
                title, kind, rent, deposit, furnish, parking, power, rating, photo = SEEDS[i % len(SEEDS)]
                n = i // len(SEEDS)
                db.execute("INSERT INTO listings(id,owner_id,title,type,rent,deposit,area,furnishing,parking,electricity_included,available_from,photo,summary,amenities,is_sample) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)", (f"RR-{i+1:03}", oid, title if n == 0 else f"{title} · {n+1}", kind, rent+n*500, deposit+n*1000, AREAS[i % len(AREAS)], furnish, parking, power, f"2026-11-{i%20+1:02}", f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1000&q=80", "A comfortable Nagpur home with useful everyday details and clear costs to help you compare options.", json.dumps([["Wi-Fi", "Study desk", "Washing machine"], ["Balcony", "Water purifier", "Wi-Fi"], ["Kitchen", "Wardrobe", "Lift"], ["Wi-Fi", "Study area", "Power backup"], ["Parking", "Balcony", "Kitchen"]][i%5])))
            first = ["Aarohi", "Vivaan", "Sana", "Arnav", "Ishita", "Rehan", "Myra", "Ayaan", "Kritika", "Kabir", "Anika", "Rohan", "Zara", "Advik", "Meher", "Ishan", "Nitya", "Shaurya", "Saira", "Neil"]
            last = ["Kadam", "Pawar", "Sharma", "Khan", "Bose", "Rao", "Joshi", "Desai", "Seth", "Kulkarni"]
            for i in range(200):
                role = "student" if i < 140 else "employee"
                occupation = (["Engineering student", "Medical student", "Design student", "Commerce student", "MBA student"] if role == "student" else ["Software engineer", "Analyst", "Teacher", "Research associate", "Healthcare professional"])[i % 5]
                db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES(?,?,?,?,?,?,1)", (f"USR-{i+1:03}", f"{first[i%20]} {last[i//20]}", f"user{i+1:03}@example.com", role, occupation, 7000+(i%9)*2000))
        return True


def remove_sample_data():
    with db_session() as db:
        db.execute("DELETE FROM inquiries WHERE listing_id IN (SELECT id FROM listings WHERE is_sample=1) OR student_id IN (SELECT id FROM users WHERE is_sample=1)")
        db.execute("DELETE FROM listings WHERE is_sample=1")
        db.execute("DELETE FROM users WHERE is_sample=1")
        db.execute("DELETE FROM owners WHERE is_sample=1")
        return True


def rows(db, sql, params=()):
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def listing_json(row):
    row["parking"] = bool(row["parking"])
    row["electricityIncluded"] = bool(row.pop("electricity_included"))
    row["ownerId"] = row.pop("owner_id")
    row["availableFrom"] = row.pop("available_from")
    row["amenities"] = json.loads(row["amenities"])
    row["isSample"] = bool(row.pop("is_sample"))
    row["city"] = "Nagpur"
    row["state"] = "Maharashtra"
    row["beds"] = 2 if row["type"] == "2 BHK flat" else 1
    row["baths"] = 2 if row["type"] == "2 BHK flat" else 1
    row["gallery"] = [row["photo"], row["photo"]]
    row["updatedDays"] = 0
    row["address"] = "Near neighborhood landmark"
    return row


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, data, status=200):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "response_cookie", None):
            self.send_header("Set-Cookie", self.response_cookie)
            self.response_cookie = None
        self.end_headers()
        self.wfile.write(raw)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https://images.unsplash.com data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def body(self):
        size = int(self.headers.get("Content-Length", 0))
        if size > 20000:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(size) or b"{}")

    def session(self, db):
        raw = next((part.strip().split("=",1)[1] for part in self.headers.get("Cookie", "").split(";") if part.strip().startswith(f"{SESSION_COOKIE}=")), None)
        if not raw:
            return None
        token_hash = __import__("hashlib").sha256(raw.encode()).hexdigest()
        row = db.execute("SELECT s.csrf_token,s.expires_at,a.id,a.email,a.name,a.role,a.is_verified FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND a.is_active=1", (token_hash,)).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            return None
        return dict(row) | {"token_hash": token_hash}

    def require_session(self, db, role=None, csrf=False):
        current = self.session(db)
        if not current:
            self.send_json({"error": "Sign in to continue."}, 401)
            return None
        if role and current["role"] != role:
            self.send_json({"error": "This action is not available for your account."}, 403)
            return None
        if csrf and (not self.headers.get("Origin") or self.headers.get("X-CSRF-Token") != current["csrf_token"]):
            self.send_json({"error": "Request could not be verified. Refresh and try again."}, 403)
            return None
        return current

    def create_session(self, db, account_id):
        raw_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        token_hash = __import__("hashlib").sha256(raw_token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        db.execute("INSERT INTO sessions(token_hash,account_id,csrf_token,expires_at) VALUES(?,?,?,?)", (token_hash, account_id, csrf_token, expires.isoformat()))
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        self.response_cookie = f"{SESSION_COOKIE}={raw_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_DAYS*86400}{secure}"
        return csrf_token

    def check_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        return bool(origin and host and urlparse(origin).netloc.lower() == host.lower())

    def do_GET(self):
        path = urlparse(self.path).path
        with db_session() as db:
            if path == "/api/listings":
                result = rows(db, "SELECT * FROM listings WHERE status='active' ORDER BY created_at DESC, id")
                owners = rows(db, "SELECT id,name,is_sample FROM owners")
                for owner in owners:
                    owner["isSample"] = bool(owner.pop("is_sample", 0))
                self.send_json({"listings": [listing_json(r) for r in result], "owners": owners})
                return
            if path == "/api/summary":
                self.send_json({"listings": db.execute("SELECT COUNT(*) FROM listings WHERE status='active'").fetchone()[0], "owners": db.execute("SELECT COUNT(*) FROM owners").fetchone()[0], "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0], "employees": db.execute("SELECT COUNT(*) FROM users WHERE role='employee'").fetchone()[0], "inquiries": db.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0], "sampleListings": db.execute("SELECT COUNT(*) FROM listings WHERE is_sample=1 AND status='active'").fetchone()[0], "sampleOwners": db.execute("SELECT COUNT(*) FROM owners WHERE is_sample=1").fetchone()[0], "sampleUsers": db.execute("SELECT COUNT(*) FROM users WHERE is_sample=1").fetchone()[0]})
                return
            if path == "/api/inquiries":
                current = self.require_session(db, role="owner")
                if not current:
                    return
                self.send_json(rows(db, "SELECT i.id,i.listing_id,i.student_id,i.message,i.status,i.created_at,l.title listing_title,u.name student_name,u.role student_role FROM inquiries i JOIN listings l ON l.id=i.listing_id JOIN users u ON u.id=i.student_id WHERE l.owner_id=? ORDER BY i.id DESC", (current["id"],)))
                return
            if path == "/api/auth/session":
                current = self.session(db)
                if current:
                    self.send_json({"user": {"id": current["id"], "email": current["email"], "name": current["name"], "role": current["role"], "isVerified": bool(current["is_verified"])}, "csrfToken": current["csrf_token"]})
                else:
                    self.send_json({"user": None, "csrfToken": None})
                return
            if path == "/" or path.startswith("/styles.css") or path.startswith("/app.js") or path.startswith("/data.js"):
                return super().do_GET()
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            payload = self.body()
            with db_session() as db:
                if self.path in {"/api/auth/register", "/api/auth/login", "/api/auth/logout"}:
                    if not self.check_origin():
                        return self.send_json({"error": "Request origin could not be verified."}, 403)
                    if self.path == "/api/auth/register":
                        name = str(payload.get("name", "")).strip()
                        email = str(payload.get("email", "")).strip().lower()
                        password = str(payload.get("password", ""))
                        role = str(payload.get("role", ""))
                        if not 2 <= len(name) <= 80 or email.count("@") != 1 or len(email) > 254 or any(char.isspace() for char in email) or role not in {"owner", "student", "employee"} or len(password) < 12 or len(password) > 256:
                            return self.send_json({"error": "Use a name, valid email, account type, and password between 12 and 256 characters."}, 400)
                        if db.execute("SELECT 1 FROM accounts WHERE email=? UNION SELECT 1 FROM owners WHERE lower(email)=? UNION SELECT 1 FROM users WHERE lower(email)=?", (email,email,email)).fetchone():
                            return self.send_json({"error": "An account with this email already exists."}, 409)
                        account_id = f"OWN-{secrets.token_hex(12)}" if role == "owner" else f"USR-{secrets.token_hex(12)}"
                        if role == "owner":
                            db.execute("INSERT INTO owners(id,name,email,is_sample) VALUES(?,?,?,0)", (account_id,name,email))
                        else:
                            db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES(?,?,?,?,?,?,0)", (account_id,name,email,role,"Not set",0))
                        db.execute("INSERT INTO accounts(id,email,name,role,password_hash) VALUES(?,?,?,?,?)", (account_id,email,name,role,PASSWORD_HASHER.hash(password)))
                        csrf = self.create_session(db, account_id)
                        self.send_json({"user":{"id":account_id,"email":email,"name":name,"role":role,"isVerified":False},"csrfToken":csrf},201)
                        return
                    if self.path == "/api/auth/login":
                        email = str(payload.get("email", "")).strip().lower()
                        password = str(payload.get("password", ""))
                        if len(email) > 254 or len(password) > 256:
                            return self.send_json({"error":"Email or password is invalid."},400)
                        ip = self.client_address[0]
                        since = (datetime.now(timezone.utc)-timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                        db.execute("DELETE FROM auth_attempts WHERE failed_at < datetime('now','-1 day')")
                        count = db.execute("SELECT COUNT(*) FROM auth_attempts WHERE ip_address=? AND email=? AND failed_at>=?",(ip,email,since)).fetchone()[0]
                        ip_count = db.execute("SELECT COUNT(*) FROM auth_attempts WHERE ip_address=? AND failed_at>=?",(ip,since)).fetchone()[0]
                        if count >= 8 or ip_count >= 30:
                            return self.send_json({"error":"Too many sign-in attempts. Try again in 15 minutes."},429)
                        account=db.execute("SELECT * FROM accounts WHERE email=? AND is_active=1",(email,)).fetchone()
                        try:
                            if not account:
                                PASSWORD_HASHER.hash("constant-time-invalid-user-check")
                                raise VerifyMismatchError
                            PASSWORD_HASHER.verify(account["password_hash"],password)
                        except (VerifyMismatchError, ValueError):
                            db.execute("INSERT INTO auth_attempts(ip_address,email) VALUES(?,?)",(ip,email[:254]))
                            return self.send_json({"error":"Email or password is incorrect."},401)
                        db.execute("DELETE FROM auth_attempts WHERE ip_address=? AND email=?",(ip,email))
                        csrf=self.create_session(db,account["id"])
                        self.send_json({"user":{"id":account["id"],"email":account["email"],"name":account["name"],"role":account["role"],"isVerified":bool(account["is_verified"])},"csrfToken":csrf})
                        return
                    current = self.require_session(db, csrf=True)
                    if not current:
                        return
                    db.execute("DELETE FROM sessions WHERE token_hash=?",(current["token_hash"],))
                    self.send_response(204)
                    self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
                    self.end_headers()
                    return
                if self.path == "/api/inquiries":
                    if not self.check_origin():
                        return self.send_json({"error": "Request origin could not be verified."}, 403)
                    current = self.require_session(db, csrf=True)
                    if not current:
                        return
                    if current["role"] not in {"student", "employee"}:
                        return self.send_json({"error":"Only renter accounts can send inquiries."},403)
                    listing_id = str(payload.get("listingId", ""))
                    message = str(payload.get("message", "")).strip()
                    student_id = current["id"]
                    if len(message) < 8 or len(message) > 2000:
                        return self.send_json({"error": "Message must be between 8 and 2,000 characters."}, 400)
                    if not db.execute("SELECT 1 FROM listings WHERE id=? AND status='active'", (listing_id,)).fetchone():
                        return self.send_json({"error": "This listing is no longer available."}, 404)
                    cursor = db.execute("INSERT INTO inquiries(listing_id,student_id,message) VALUES(?,?,?)", (listing_id, student_id, message))
                    return self.send_json({"id": cursor.lastrowid, "message": "Inquiry saved to the local preview inbox."}, 201)
                if self.path == "/api/listings":
                    if not self.check_origin():
                        return self.send_json({"error": "Request origin could not be verified."}, 403)
                    current = self.require_session(db, role="owner", csrf=True)
                    if not current:
                        return
                    title = str(payload.get("title", "")).strip()
                    kind = str(payload.get("type", ""))
                    area = str(payload.get("area", ""))
                    rent, deposit = int(payload.get("rent", 0)), int(payload.get("deposit", 0))
                    if not title or len(title) > 100 or kind not in {"Private room", "Shared room", "1 BHK flat", "2 BHK flat"} or area not in AREAS or rent < 1 or rent > 1000000 or deposit < 0 or deposit > 10000000:
                        return self.send_json({"error": "Enter a title, valid property type, Nagpur area, and realistic rent and deposit."}, 400)
                    new_id = f"RR-{secrets.token_hex(12)}"
                    db.execute("INSERT INTO listings(id,owner_id,title,type,rent,deposit,area,furnishing,parking,electricity_included,available_from,photo,summary,amenities,is_sample) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)", (new_id, current["id"], title, kind, rent, deposit, area, str(payload.get("furnishing", "Semi furnished")), int(payload.get("parking") is True), int(payload.get("electricityIncluded") is True), str(payload.get("availableFrom", "2026-11-01")), "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1000&q=80", str(payload.get("summary", ""))[:500], json.dumps([])))
                    return self.send_json({"id": new_id, "message": "Listing added to the local preview."}, 201)
            self.send_json({"error": "Not found"}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": f"Invalid request: {exc}"}, 400)
        except Exception:
            traceback.print_exc()
            self.send_json({"error": "The request could not be completed."}, 500)

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run or manage the RoomRoute local preview")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--seed-sample-data", action="store_true", help="Add clearly tagged sample owners, listings, and renter profiles")
    action.add_argument("--remove-sample-data", action="store_true", help="Delete sample inquiries, listings, owners, and renter profiles")
    args = parser.parse_args()
    init_db()
    if args.seed_sample_data:
        print("Sample data loaded." if seed_sample_data() else "Sample data is already loaded; no records changed.")
        raise SystemExit(0)
    if args.remove_sample_data:
        remove_sample_data()
        print("Sample records removed. User-created non-sample records were retained.")
        raise SystemExit(0)
    if os.environ.get("APP_ENV", "development").lower() == "production":
        raise SystemExit("Production mode is disabled: this build still needs authentication, owner verification, PostgreSQL, and deployment hardening. Do not expose the local preview server to the internet.")
    host = os.environ.get("ROOMROUTE_HOST", "127.0.0.1")
    port = int(os.environ.get("ROOMROUTE_PORT", "8765"))
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This preview server is local-only and refuses non-loopback bind addresses.")
    if os.environ.get("ROOMROUTE_SEED_DATA", "0") == "1":
        print("Sample data loaded." if seed_sample_data() else "Sample data already present.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"RoomRoute local preview: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRoomRoute stopped.")

