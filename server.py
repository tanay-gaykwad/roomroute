"""Loopback-only RoomRoute product preview server."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import threading
import time
import traceback
from email.message import EmailMessage
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from datetime import date, datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("ROOMROUTE_DB_PATH", str(ROOT / "roomroute.sqlite3"))).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))
_pg_pool = None
_pool_lock = threading.Lock()
_redis_client = None
_redis_url_bound = None
_redis_lock = threading.Lock()
AREAS = ["Dharampeth", "Bajaj Nagar", "Laxmi Nagar", "Pratap Nagar", "Manish Nagar", "Trimurti Nagar", "Ramdaspeth", "Civil Lines", "Sadar", "Wardha Road"]
NAMES = ["Aarav Deshmukh", "Meera Kulkarni", "Rohan Patil", "Ananya Joshi", "Siddharth Shah", "Isha Nair", "Kabir Rao", "Neha Gokhale", "Aditya Sinha", "Tanvi Bapat", "Vihaan More", "Sana Khan", "Arjun Reddy", "Mira Chavan", "Dev Malhotra", "Riya Korde", "Ishaan Kulkarni", "Nisha Jadhav", "Omkar Desai", "Tara Menon", "Kunal Bhosale", "Aditi Puri", "Reyansh Pawar", "Zoya Merchant", "Atharv Kale", "Diya Shah", "Neil Wankhede", "Pooja Thakur", "Yash Mehta", "Saanvi Gupte", "Parth Agrawal", "Kavya Pillai", "Rudra Dube", "Simran Kaur", "Manav Borkar", "Anvi Rane", "Dhruv Jain", "Leena Naidu", "Ayaan Sheikh", "Sia Vaidya", "Harsh Tiwari", "Mahi Sable", "Nikhil Kamat", "Ira Roy", "Pranav Bhandari", "Esha Soni", "Samar Gawande", "Rhea Dutta", "Aarush Naik", "Tiya Mishra"]
SEEDS = [
    ("Sunlit room in a calm shared home", "Private room", 10500, 21000, "Fully furnished", 1, 1, "photo-1522708323590-d24dbb6b0267"),
    ("A bright room, steps from campus", "Private room", 8500, 17000, "Semi furnished", 0, 0, "photo-1505693416388-ac5ce068fe85"),
    ("Easy living in a roomy 2 BHK", "2 BHK flat", 22000, 44000, "Fully furnished", 1, 1, "photo-1600210492486-724fe5c67fb0"),
    ("Shared space with a friendly vibe", "Shared room", 6000, 12000, "Fully furnished", 1, 0, "photo-1600607687939-ce8a6c25118c"),
    ("A little home near the green", "1 BHK flat", 15500, 30000, "Semi furnished", 1, 1, "photo-1600566753086-00f18fb6b3ea"),
    ("Quiet private room with a balcony", "Private room", 12000, 24000, "Fully furnished", 0, 1, "photo-1600607687920-4e2a09cf159d"),
    ("Your own corner in a shared flat", "Private room", 9000, 18000, "Semi furnished", 1, 0, "photo-1600566753190-17f0baa2a6c3"),
    ("Open, airy 2 BHK near the main road", "2 BHK flat", 25000, 50000, "Fully furnished", 1, 1, "photo-1616486338812-3dadae4b4ace"),
    ("Comfortable shared room, all set up", "Shared room", 5500, 11000, "Fully furnished", 0, 0, "photo-1600585154340-be6161a56a0c"),
    ("A neat 1 BHK for your next chapter", "1 BHK flat", 14500, 29000, "Unfurnished", 1, 1, "photo-1600607687644-c7171b42498f"),
]
PASSWORD_HASHER = PasswordHasher()
SESSION_COOKIE = "roomroute_session"
SESSION_DAYS = 7
MAX_REQUEST_BYTES = 20_000
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z]{2,63})+$")


class HybridRow(dict):
    """Mapping rows that retain sqlite-style positional access."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class PgConnection:
    def __init__(self, raw, pool): self.raw, self.pool = raw, pool
    def execute(self, sql, params=()):
        return self.raw.execute(sql.replace("?", "%s"), params)
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.pool.putconn(self.raw)


def redis_connection():
    global _redis_client, _redis_url_bound
    redis_url=os.environ.get("REDIS_URL","").strip()
    if not redis_url: return None
    with _redis_lock:
        if _redis_client is None or _redis_url_bound!=redis_url:
            import redis
            _redis_client=redis.Redis.from_url(redis_url,socket_connect_timeout=2,socket_timeout=2,decode_responses=True)
            _redis_url_bound=redis_url
    return _redis_client


def connect():
    if IS_POSTGRES:
        try:
            import psycopg
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError("Install psycopg[binary] to use PostgreSQL") from exc
        global _pg_pool
        normalized_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
        with _pool_lock:
            if _pg_pool is None:
                pool_size=max(1,min(64,int(os.environ.get("ROOMROUTE_DB_POOL_SIZE","20"))))
                _pg_pool=ConnectionPool(normalized_url,min_size=1,max_size=pool_size,timeout=10,kwargs={"row_factory":_hybrid_factory},open=True)
        return PgConnection(_pg_pool.getconn(),_pg_pool)
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _hybrid_factory(cursor):
    # DDL and other command statements have no row description. Psycopg
    # requests a row maker for them anyway, so return a no-op maker.
    if cursor.description is None:
        return lambda values: None
    names = [column.name for column in cursor.description]
    return lambda values: HybridRow(zip(names, values))


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


def database_now():
    now = datetime.now(timezone.utc)
    return now if IS_POSTGRES else now.isoformat()


def queue_email(db, recipient, subject, body):
    db.execute("INSERT INTO email_outbox(recipient,subject,body) VALUES(?,?,?)", (recipient, subject, body))


def deliver_pending_email(db, limit=20):
    """Deliver durable mail jobs with bounded retries; secrets stay in environment."""
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        if os.environ.get("APP_ENV", "development").lower() == "production":
            raise RuntimeError("SMTP_HOST is required in production")
        pending=rows(db,"SELECT * FROM email_outbox WHERE sent_at IS NULL AND next_attempt<=? ORDER BY id LIMIT ?",(database_now(),limit))
        for item in pending:
            print(f"[LOCAL EMAIL PREVIEW] To: {item['recipient']} | Subject: {item['subject']}\n{item['body']}")
            db.execute("UPDATE email_outbox SET sent_at=?,body='' WHERE id=?",(database_now(),item["id"]))
        return len(pending)
    now = database_now()
    lock_clause = " FOR UPDATE SKIP LOCKED" if IS_POSTGRES else ""
    rows_to_send = rows(db, "SELECT * FROM email_outbox WHERE sent_at IS NULL AND next_attempt<=? ORDER BY id LIMIT ?" + lock_clause, (now, limit))
    sent = 0
    for item in rows_to_send:
        message = EmailMessage()
        message["Subject"] = item["subject"]
        message["From"] = os.environ.get("SMTP_FROM", "RoomRoute <no-reply@localhost>")
        message["To"] = item["recipient"]
        message.set_content(item["body"])
        try:
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=10) as client:
                client.ehlo()
                if os.environ.get("SMTP_STARTTLS", "1") == "1":
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                username = os.environ.get("SMTP_USERNAME", "")
                if username:
                    client.login(username, os.environ.get("SMTP_PASSWORD", ""))
                client.send_message(message)
            db.execute("UPDATE email_outbox SET sent_at=?,last_error=NULL,body='' WHERE id=?", (database_now(), item["id"]))
            sent += 1
        except Exception as exc:
            attempts = int(item["attempts"]) + 1
            delay = min(3600, 30 * (2 ** min(attempts, 7)))
            retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
            retry = retry if IS_POSTGRES else retry.isoformat()
            db.execute("UPDATE email_outbox SET attempts=?,next_attempt=?,last_error=? WHERE id=?", (attempts, retry, type(exc).__name__[:100], item["id"]))
    # Remove delivered message bodies and metadata after a short audit window.
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    cutoff = cutoff if IS_POSTGRES else cutoff.isoformat()
    db.execute("DELETE FROM email_outbox WHERE sent_at IS NOT NULL AND sent_at<?", (cutoff,))
    expired = datetime.now(timezone.utc)-timedelta(days=1)
    expired = expired if IS_POSTGRES else expired.isoformat()
    db.execute("DELETE FROM auth_tokens WHERE expires_at<?", (expired,))
    db.execute("DELETE FROM sessions WHERE expires_at<?", (expired,))
    return sent


def init_db():
    if IS_POSTGRES:
        with db_session() as db:
            statements = [
                "CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS owners(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,role TEXT NOT NULL DEFAULT 'owner',is_sample INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,role TEXT NOT NULL,occupation TEXT NOT NULL,budget INTEGER NOT NULL,is_sample INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL REFERENCES owners(id),title TEXT NOT NULL,type TEXT NOT NULL,rent INTEGER NOT NULL,deposit INTEGER NOT NULL,area TEXT NOT NULL,city TEXT NOT NULL DEFAULT 'Nagpur',furnishing TEXT NOT NULL,parking INTEGER NOT NULL,electricity_included INTEGER NOT NULL,available_from TEXT NOT NULL,photo TEXT NOT NULL,summary TEXT NOT NULL,amenities TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',is_sample INTEGER NOT NULL DEFAULT 0,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),moderation_note TEXT)",
                "CREATE TABLE IF NOT EXISTS inquiries(id BIGSERIAL PRIMARY KEY,listing_id TEXT NOT NULL REFERENCES listings(id),student_id TEXT NOT NULL REFERENCES users(id),message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'new',created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('owner','student','employee','moderator')),password_hash TEXT NOT NULL,is_verified INTEGER NOT NULL DEFAULT 0,is_active INTEGER NOT NULL DEFAULT 1,created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,csrf_token TEXT NOT NULL,expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS auth_attempts(id BIGSERIAL PRIMARY KEY,ip_address TEXT NOT NULL,email TEXT NOT NULL,failed_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS request_limits(id BIGSERIAL PRIMARY KEY,action TEXT NOT NULL,ip_address TEXT NOT NULL,occurred_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS auth_tokens(token_hash TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,purpose TEXT NOT NULL,expires_at TIMESTAMPTZ NOT NULL,used_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS email_outbox(id BIGSERIAL PRIMARY KEY,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,next_attempt TIMESTAMPTZ NOT NULL DEFAULT now(),sent_at TIMESTAMPTZ,last_error TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE TABLE IF NOT EXISTS listing_reports(id BIGSERIAL PRIMARY KEY,listing_id TEXT NOT NULL REFERENCES listings(id),reporter_id TEXT NOT NULL REFERENCES accounts(id),reason TEXT NOT NULL,details TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'open',created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
                "CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_auth_tokens_active ON auth_tokens(account_id,purpose,expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_outbox_pending ON email_outbox(sent_at,next_attempt)",
                "CREATE INDEX IF NOT EXISTS idx_reports_status ON listing_reports(status,created_at)",
                "CREATE INDEX IF NOT EXISTS idx_auth_attempts_lookup ON auth_attempts(ip_address,email,failed_at)",
                "CREATE INDEX IF NOT EXISTS idx_listings_public_order ON listings(status,created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_inquiries_listing_order ON inquiries(listing_id,id DESC)",
                "CREATE INDEX IF NOT EXISTS idx_inquiries_student ON inquiries(student_id)",
            ]
            for statement in statements: db.execute(statement)
            # Existing installations receive additive-only schema upgrades.
            db.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS moderation_note TEXT")
            db.execute("ALTER TABLE listings ALTER COLUMN status SET DEFAULT 'pending'")
            db.execute("INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT(version) DO NOTHING")
            if not db.execute("SELECT 1 FROM schema_migrations WHERE version=2").fetchone():
                db.execute("UPDATE listings SET status='pending' WHERE is_sample=0 AND status='active'")
                db.execute("INSERT INTO schema_migrations(version) VALUES(2) ON CONFLICT(version) DO NOTHING")
        return
    with db_session() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS owners(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL DEFAULT 'owner', is_sample INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL, occupation TEXT NOT NULL, budget INTEGER NOT NULL, is_sample INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owners(id), title TEXT NOT NULL, type TEXT NOT NULL, rent INTEGER NOT NULL, deposit INTEGER NOT NULL, area TEXT NOT NULL, city TEXT NOT NULL DEFAULT 'Nagpur', furnishing TEXT NOT NULL, parking INTEGER NOT NULL, electricity_included INTEGER NOT NULL, available_from TEXT NOT NULL, photo TEXT NOT NULL, summary TEXT NOT NULL, amenities TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', is_sample INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, moderation_note TEXT);
        CREATE TABLE IF NOT EXISTS inquiries(id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id TEXT NOT NULL REFERENCES listings(id), student_id TEXT NOT NULL REFERENCES users(id), message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','student','employee','moderator')), password_hash TEXT NOT NULL, is_verified INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS auth_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT NOT NULL, email TEXT NOT NULL, failed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS request_limits(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, ip_address TEXT NOT NULL, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS auth_tokens(token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, purpose TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS email_outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT, last_error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS listing_reports(id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id TEXT NOT NULL REFERENCES listings(id), reporter_id TEXT NOT NULL REFERENCES accounts(id), reason TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_auth_attempts_lookup ON auth_attempts(ip_address,email,failed_at);
        CREATE INDEX IF NOT EXISTS idx_request_limits_lookup ON request_limits(action,ip_address,occurred_at);
        CREATE INDEX IF NOT EXISTS idx_listings_public_order ON listings(status,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_inquiries_listing_order ON inquiries(listing_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_inquiries_student ON inquiries(student_id);
        """)
        # Safe migrations for databases created by the earlier local preview.
        for table in ("owners", "users", "listings"):
            columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            if "is_sample" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
                db.execute(f"UPDATE {table} SET is_sample=1")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(listings)")}
        if "moderation_note" not in columns:
            db.execute("ALTER TABLE listings ADD COLUMN moderation_note TEXT")
        db.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES(1)")
        if not db.execute("SELECT 1 FROM schema_migrations WHERE version=2").fetchone():
            db.execute("UPDATE listings SET status='pending' WHERE is_sample=0 AND status='active'")
            db.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES(2)")


def seed_sample_data():
    with db_session() as db:
        sample_rows = sum(db.execute(f"SELECT COUNT(*) FROM {table} WHERE is_sample=1").fetchone()[0] for table in ("owners", "users", "listings"))
        if sample_rows:
            return False
        real_rows = sum(db.execute(f"SELECT COUNT(*) FROM {table} WHERE is_sample=0").fetchone()[0] for table in ("owners", "users", "listings"))
        real_rows += db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        if real_rows:
            raise RuntimeError("Sample records can only be seeded into an empty database. Existing user data was left unchanged.")
        for i, name in enumerate(NAMES):
            oid = f"OWN-{i+1:03}"
            db.execute("INSERT INTO owners(id,name,email,is_sample) VALUES(?,?,?,1)", (oid, name, f"owner{i+1:03}@example.com"))
            title, kind, rent, deposit, furnish, parking, power, photo = SEEDS[i % len(SEEDS)]
            n = i // len(SEEDS)
            db.execute("INSERT INTO listings(id,owner_id,title,type,rent,deposit,area,furnishing,parking,electricity_included,available_from,photo,summary,amenities,is_sample) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)", (f"RR-{i+1:03}", oid, title if n == 0 else f"{title} · {n+1}", kind, rent+n*500, deposit+n*1000, AREAS[i % len(AREAS)], furnish, parking, power, f"2026-11-{i%20+1:02}", f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1000&q=80", "A comfortable Nagpur home with useful everyday details and clear costs to help you compare options.", json.dumps([["Wi-Fi", "Study desk", "Washing machine"], ["Balcony", "Water purifier", "Wi-Fi"], ["Kitchen", "Wardrobe", "Lift"], ["Wi-Fi", "Study area", "Power backup"], ["Parking", "Balcony", "Kitchen"]][i%5])))
        first = ["Aarohi", "Vivaan", "Sana", "Arnav", "Ishita", "Rehan", "Myra", "Ayaan", "Kritika", "Kabir", "Anika", "Rohan", "Zara", "Advik", "Meher", "Ishan", "Nitya", "Shaurya", "Saira", "Neil"]
        last = ["Kadam", "Pawar", "Sharma", "Khan", "Bose", "Rao", "Joshi", "Desai", "Seth", "Kulkarni"]
        for i in range(200):
            role = "student" if i < 140 else "employee"
            occupation = (["Engineering student", "Medical student", "Design student", "Commerce student", "MBA student"] if role == "student" else ["Software engineer", "Analyst", "Teacher", "Research associate", "Healthcare professional"])[i % 5]
            db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES(?,?,?,?,?,?,1)", (f"USR-{i+1:03}", f"{first[i%20]} {last[i//20]}", f"user{i+1:03}@example.com", role, occupation, 7000+(i%9)*2000))
        db.execute("UPDATE listings SET status='active' WHERE is_sample=1")
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
    row.pop("moderation_note",None)
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
        raw = json.dumps(data, default=lambda value: value.isoformat() if isinstance(value, (datetime, date)) else str(value)).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "response_cookie", None):
            self.send_header("Set-Cookie", self.response_cookie)
            self.response_cookie = None
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def cookie_name():
        return "__Host-roomroute_session" if os.environ.get("APP_ENV", "development").lower() == "production" else SESSION_COOKIE

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https://images.unsplash.com data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if os.environ.get("APP_ENV", "development").lower() == "production":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are not supported")
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise ValueError("Content-Type must be application/json")
        raw_size = self.headers.get("Content-Length")
        if raw_size is None or not raw_size.isdecimal():
            raise ValueError("A valid Content-Length header is required")
        size = int(raw_size)
        if size > MAX_REQUEST_BYTES:
            raise ValueError("Request is too large")
        payload = json.loads(self.rfile.read(size))
        if not isinstance(payload, dict):
            raise ValueError("A JSON object is required")
        return payload

    def allow_write(self, db, action, limit, window_seconds):
        """Use Redis atomics in service deployments; SQLite is for local preview only."""
        ip = self.client_ip()
        redis_url = os.environ.get("REDIS_URL", "").strip()
        if redis_url:
            try:
                client = redis_connection()
                key = f"roomroute:limit:{action}:{ip}"
                # One atomic increment-and-expire operation shared by all app workers.
                count = client.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]); end; return n", 1, key, int(window_seconds))
                return int(count) <= limit
            except Exception:
                if os.environ.get("APP_ENV", "development").lower() == "production":
                    raise RuntimeError("Distributed rate limiter is unavailable")
                return False
        if os.environ.get("APP_ENV", "development").lower() == "production":
            raise RuntimeError("REDIS_URL is required in production")
        since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        if not IS_POSTGRES: since=since.strftime("%Y-%m-%d %H:%M:%S")
        count = db.execute("SELECT COUNT(*) FROM request_limits WHERE action=? AND ip_address=? AND occurred_at>=?", (action, ip, since)).fetchone()[0]
        if count >= limit:
            return False
        db.execute("INSERT INTO request_limits(action,ip_address) VALUES(?,?)", (action, ip))
        db.execute("DELETE FROM request_limits WHERE occurred_at < ?", ((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),))
        return True

    def client_ip(self):
        peer = self.client_address[0]
        try: peer_ip=ipaddress.ip_address(peer)
        except ValueError: return peer
        trusted=[]
        for value in os.environ.get("ROOMROUTE_TRUST_PROXY_CIDRS","").split(","):
            try: trusted.append(ipaddress.ip_network(value.strip(),strict=False))
            except ValueError: continue
        if not any(peer_ip in network for network in trusted): return peer
        forwarded=[part.strip() for part in self.headers.get("X-Forwarded-For","").split(",") if part.strip()]
        chain=forwarded+[peer]
        client=peer
        for candidate in reversed(chain):
            try: address=ipaddress.ip_address(candidate)
            except ValueError: break
            if not any(address in network for network in trusted):
                client=candidate
                break
        return client

    def trusted_host(self):
        configured = os.environ.get("ROOMROUTE_ALLOWED_HOSTS", "")
        if os.environ.get("APP_ENV", "development").lower() == "production":
            allowed = {value.strip().lower() for value in configured.split(",") if value.strip()}
            return bool(allowed and self.headers.get("Host", "").split(":")[0].lower() in allowed)
        port = os.environ.get("ROOMROUTE_PORT", "8765")
        allowed = {f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"}
        return self.headers.get("Host", "").lower() in allowed

    def session(self, db):
        cookie_name = self.cookie_name()
        raw = next((part.strip().split("=",1)[1] for part in self.headers.get("Cookie", "").split(";") if part.strip().startswith(f"{cookie_name}=")), None)
        if not raw:
            return None
        token_hash = __import__("hashlib").sha256(raw.encode()).hexdigest()
        row = db.execute("SELECT s.csrf_token,s.expires_at,a.id,a.email,a.name,a.role,a.is_verified FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND a.is_active=1", (token_hash,)).fetchone()
        if not row:
            return None
        expiry = row["expires_at"]
        expiry = expiry if isinstance(expiry, datetime) else datetime.fromisoformat(expiry)
        if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
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
        # Never derive cookie security from a client-controlled forwarded header.
        production = os.environ.get("APP_ENV", "development").lower() == "production"
        cookie_name = self.cookie_name()
        secure = "; Secure" if production else ""
        self.response_cookie = f"{cookie_name}={raw_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_DAYS*86400}{secure}"
        return csrf_token

    def check_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        parsed = urlparse(origin or "")
        production = os.environ.get("APP_ENV", "development").lower() == "production"
        return bool(self.trusted_host() and parsed.scheme in ({"https"} if production else {"http", "https"}) and parsed.netloc and host and parsed.netloc.lower() == host.lower())

    def do_GET(self):
        if not self.trusted_host():
            return self.send_json({"error": "Host is not allowed."}, 421)
        path = urlparse(self.path).path
        if path == "/healthz":
            try:
                with db_session() as db:
                    db.execute("SELECT 1")
                if os.environ.get("APP_ENV", "development").lower() == "production":
                    redis_connection().ping()
                return self.send_json({"status": "ok"})
            except Exception:
                return self.send_json({"status": "unavailable"}, 503)
        with db_session() as db:
            if path == "/api/listings":
                result = rows(db, "SELECT * FROM listings WHERE status='active' ORDER BY created_at DESC, id")
                owners = rows(db, "SELECT DISTINCT o.id,o.name,o.is_sample FROM owners o JOIN listings l ON l.owner_id=o.id WHERE l.status='active'")
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
            if path == "/api/owner/listings":
                current=self.require_session(db,role="owner")
                if not current: return
                self.send_json(rows(db,"SELECT id,title,type,rent,deposit,area,available_from,status,moderation_note,is_sample FROM listings WHERE owner_id=? ORDER BY created_at DESC",(current["id"],)))
                return
            if path == "/api/account/export":
                current = self.require_session(db)
                if not current: return
                profile = db.execute("SELECT name,email,role,is_verified,created_at FROM accounts WHERE id=?", (current["id"],)).fetchone()
                renter_profile = db.execute("SELECT occupation,budget FROM users WHERE id=?", (current["id"],)).fetchone()
                user_listings = rows(db, "SELECT id,title,type,rent,deposit,area,available_from,status,created_at FROM listings WHERE owner_id=?", (current["id"],))
                messages = rows(db, "SELECT i.id,i.listing_id,i.message,i.status,i.created_at,l.title FROM inquiries i JOIN listings l ON l.id=i.listing_id WHERE i.student_id=?", (current["id"],))
                reports = rows(db,"SELECT listing_id,reason,details,status,created_at FROM listing_reports WHERE reporter_id=?",(current["id"],))
                self.send_json({"account": dict(profile) if profile else {}, "renterProfile":dict(renter_profile) if renter_profile else None, "listings": user_listings, "inquiries": messages, "reports":reports})
                return
            if path in {"/api/moderation/listings", "/api/moderation/reports"}:
                current = self.require_session(db, role="moderator")
                if not current: return
                if path.endswith("listings"):
                    self.send_json(rows(db, "SELECT l.*,o.name owner_name,o.email owner_email FROM listings l JOIN owners o ON o.id=l.owner_id WHERE l.is_sample=0 AND l.status IN ('pending','rejected') ORDER BY l.created_at"))
                else:
                    self.send_json(rows(db, "SELECT r.*,l.title listing_title,a.email reporter_email FROM listing_reports r JOIN listings l ON l.id=r.listing_id JOIN accounts a ON a.id=r.reporter_id WHERE r.status='open' ORDER BY r.created_at"))
                return
            if path == "/api/auth/session":
                current = self.session(db)
                if current:
                    self.send_json({"user": {"id": current["id"], "email": current["email"], "name": current["name"], "role": current["role"], "isVerified": bool(current["is_verified"])}, "csrfToken": current["csrf_token"]})
                else:
                    self.send_json({"user": None, "csrfToken": None})
                return
            if path in {"/", "/styles.css", "/app.js", "/data.js"}:
                return super().do_GET()
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            if not self.trusted_host():
                return self.send_json({"error": "Host is not allowed."}, 421)
            payload = self.body()
            with db_session() as db:
                path = urlparse(self.path).path
                auth_paths = {"/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/verify", "/api/auth/resend-verification", "/api/auth/password-reset/request", "/api/auth/password-reset/complete", "/api/account/delete"}
                if path in auth_paths:
                    if not self.check_origin():
                        return self.send_json({"error": "Request origin could not be verified."}, 403)
                    if path == "/api/auth/register":
                        if not self.allow_write(db, "register", 5, 3600):
                            return self.send_json({"error": "Too many account creation attempts. Try again later."}, 429)
                        name = str(payload.get("name", "")).strip()
                        email = str(payload.get("email", "")).strip().lower()
                        password = str(payload.get("password", ""))
                        role = str(payload.get("role", ""))
                        if not 2 <= len(name) <= 80 or len(email) > 254 or not EMAIL_RE.fullmatch(email) or ".." in email.split("@")[0] or email.split("@")[0].startswith(".") or email.split("@")[0].endswith(".") or role not in {"owner", "student", "employee"} or len(password) < 12 or len(password) > 256:
                            return self.send_json({"error": "Use a name, valid email, account type, and password between 12 and 256 characters."}, 400)
                        if db.execute("SELECT 1 FROM accounts WHERE email=? UNION SELECT 1 FROM owners WHERE lower(email)=? UNION SELECT 1 FROM users WHERE lower(email)=?", (email,email,email)).fetchone():
                            return self.send_json({"error": "An account with this email already exists."}, 409)
                        account_id = f"OWN-{secrets.token_hex(12)}" if role == "owner" else f"USR-{secrets.token_hex(12)}"
                        if role == "owner":
                            db.execute("INSERT INTO owners(id,name,email,is_sample) VALUES(?,?,?,0)", (account_id,name,email))
                        else:
                            db.execute("INSERT INTO users(id,name,email,role,occupation,budget,is_sample) VALUES(?,?,?,?,?,?,0)", (account_id,name,email,role,"Not set",0))
                        db.execute("INSERT INTO accounts(id,email,name,role,password_hash) VALUES(?,?,?,?,?)", (account_id,email,name,role,PASSWORD_HASHER.hash(password)))
                        raw_token = secrets.token_urlsafe(32)
                        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
                        expires = datetime.now(timezone.utc) + timedelta(hours=24)
                        db.execute("INSERT INTO auth_tokens(token_hash,account_id,purpose,expires_at) VALUES(?,?,?,?)", (token_hash,account_id,"verify",expires if IS_POSTGRES else expires.isoformat()))
                        base_url = os.environ.get("ROOMROUTE_PUBLIC_URL", "http://127.0.0.1:8765").rstrip("/")
                        queue_email(db,email,"Verify your RoomRoute account",f"Hello {name},\n\nVerify your email within 24 hours: {base_url}/?verify={raw_token}\n\nIf you did not create this account, ignore this message.")
                        self.send_json({"message":"Check your email for a verification link. You can sign in after verifying your account."},201)
                        return
                    if path == "/api/auth/verify":
                        raw_token = str(payload.get("token", ""))
                        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
                        claim=db.execute("UPDATE auth_tokens SET used_at=? WHERE token_hash=? AND purpose='verify' AND used_at IS NULL AND expires_at>? RETURNING account_id",(database_now(),token_hash,database_now())).fetchone()
                        if not claim: return self.send_json({"error":"This verification link is invalid, expired, or already used."},400)
                        db.execute("UPDATE accounts SET is_verified=1 WHERE id=?", (claim["account_id"],))
                        db.execute("UPDATE auth_tokens SET used_at=? WHERE account_id=? AND purpose='verify' AND used_at IS NULL",(database_now(),claim["account_id"]))
                        return self.send_json({"message":"Email verified. You can now sign in."})
                    if path == "/api/auth/resend-verification":
                        if not self.allow_write(db,"resend_verification",5,3600): return self.send_json({"error":"Try again later."},429)
                        email = str(payload.get("email", "")).strip().lower()
                        target_key=hashlib.sha256(email.encode()).hexdigest()[:32]
                        if not self.allow_write(db,f"resend_target:{target_key}",3,3600):
                            return self.send_json({"message":"If an unverified account exists, a verification link has been sent."})
                        account = db.execute("SELECT id,name,email,is_verified FROM accounts WHERE email=? AND is_active=1", (email,)).fetchone()
                        if account and not account["is_verified"]:
                            raw_token=secrets.token_urlsafe(32); token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
                            expires=datetime.now(timezone.utc)+timedelta(hours=24)
                            db.execute("UPDATE auth_tokens SET used_at=? WHERE account_id=? AND purpose='verify' AND used_at IS NULL",(database_now(),account["id"]))
                            db.execute("INSERT INTO auth_tokens(token_hash,account_id,purpose,expires_at) VALUES(?,?,?,?)", (token_hash,account["id"],"verify",expires if IS_POSTGRES else expires.isoformat()))
                            base_url=os.environ.get("ROOMROUTE_PUBLIC_URL","http://127.0.0.1:8765").rstrip("/")
                            queue_email(db,email,"Verify your RoomRoute account",f"Hello {account['name']},\n\nVerify your email: {base_url}/?verify={raw_token}")
                        return self.send_json({"message":"If an unverified account exists, a verification link has been sent."})
                    if path == "/api/auth/password-reset/request":
                        if not self.allow_write(db,"password_reset",5,3600): return self.send_json({"error":"Try again later."},429)
                        email=str(payload.get("email"," ")).strip().lower()
                        target_key=hashlib.sha256(email.encode()).hexdigest()[:32]
                        if not self.allow_write(db,f"password_reset_target:{target_key}",3,3600):
                            return self.send_json({"message":"If an account exists for that email, password reset instructions have been sent."})
                        account=db.execute("SELECT id,name,email FROM accounts WHERE email=? AND is_active=1",(email,)).fetchone()
                        if account:
                            raw_token=secrets.token_urlsafe(32); token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
                            expires=datetime.now(timezone.utc)+timedelta(minutes=30)
                            db.execute("UPDATE auth_tokens SET used_at=? WHERE account_id=? AND purpose='reset' AND used_at IS NULL",(database_now(),account["id"]))
                            db.execute("INSERT INTO auth_tokens(token_hash,account_id,purpose,expires_at) VALUES(?,?,?,?)",(token_hash,account["id"],"reset",expires if IS_POSTGRES else expires.isoformat()))
                            base_url=os.environ.get("ROOMROUTE_PUBLIC_URL","http://127.0.0.1:8765").rstrip("/")
                            queue_email(db,email,"Reset your RoomRoute password",f"Hello {account['name']},\n\nReset your password within 30 minutes: {base_url}/?reset={raw_token}\n\nIf you did not request this, ignore this message.")
                        return self.send_json({"message":"If an account exists for that email, password reset instructions have been sent."})
                    if path == "/api/auth/password-reset/complete":
                        raw_token=str(payload.get("token","")); password=str(payload.get("password",""))
                        if len(password)<12 or len(password)>256: return self.send_json({"error":"Password must be between 12 and 256 characters."},400)
                        token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
                        claim=db.execute("UPDATE auth_tokens SET used_at=? WHERE token_hash=? AND purpose='reset' AND used_at IS NULL AND expires_at>? RETURNING account_id",(database_now(),token_hash,database_now())).fetchone()
                        if not claim: return self.send_json({"error":"This reset link is invalid, expired, or already used."},400)
                        db.execute("UPDATE accounts SET password_hash=? WHERE id=?",(PASSWORD_HASHER.hash(password),claim["account_id"]))
                        db.execute("DELETE FROM sessions WHERE account_id=?",(claim["account_id"],))
                        return self.send_json({"message":"Password updated. Sign in with your new password."})
                    if path == "/api/account/delete":
                        current=self.require_session(db,csrf=True)
                        if not current: return
                        account=db.execute("SELECT password_hash FROM accounts WHERE id=?",(current["id"],)).fetchone()
                        try: PASSWORD_HASHER.verify(account["password_hash"],str(payload.get("password","")))
                        except (VerifyMismatchError,ValueError): return self.send_json({"error":"Password is incorrect."},403)
                        db.execute("DELETE FROM inquiries WHERE listing_id IN (SELECT id FROM listings WHERE owner_id=?) OR student_id=?",(current["id"],current["id"]))
                        db.execute("DELETE FROM email_outbox WHERE recipient=?",(current["email"],))
                        db.execute("DELETE FROM auth_attempts WHERE lower(email)=?",(current["email"],))
                        db.execute("DELETE FROM listing_reports WHERE reporter_id=? OR listing_id IN (SELECT id FROM listings WHERE owner_id=?)",(current["id"],current["id"]))
                        db.execute("DELETE FROM listings WHERE owner_id=?",(current["id"],))
                        db.execute("DELETE FROM auth_tokens WHERE account_id=?",(current["id"],))
                        db.execute("DELETE FROM owners WHERE id=?",(current["id"],))
                        db.execute("DELETE FROM users WHERE id=?",(current["id"],))
                        db.execute("DELETE FROM accounts WHERE id=?",(current["id"],))
                        self.response_cookie=f"{self.cookie_name()}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" + ("; Secure" if os.environ.get("APP_ENV","development").lower()=="production" else "")
                        return self.send_json({"message":"Your account and associated profile data were deleted."})
                    if path == "/api/auth/login":
                        email = str(payload.get("email", "")).strip().lower()
                        password = str(payload.get("password", ""))
                        if len(email) > 254 or len(password) > 256:
                            return self.send_json({"error":"Email or password is invalid."},400)
                        ip = self.client_ip()
                        since = datetime.now(timezone.utc)-timedelta(minutes=15)
                        if not IS_POSTGRES: since=since.strftime("%Y-%m-%d %H:%M:%S")
                        db.execute("DELETE FROM auth_attempts WHERE failed_at < ?",(datetime.now(timezone.utc)-timedelta(days=1) if IS_POSTGRES else (datetime.now(timezone.utc)-timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),))
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
                        if not account["is_verified"]:
                            return self.send_json({"error":"Verify your email before signing in. You can request a new link."},403)
                        db.execute("DELETE FROM auth_attempts WHERE ip_address=? AND email=?",(ip,email))
                        csrf=self.create_session(db,account["id"])
                        self.send_json({"user":{"id":account["id"],"email":account["email"],"name":account["name"],"role":account["role"],"isVerified":bool(account["is_verified"])},"csrfToken":csrf})
                        return
                    current = self.require_session(db, csrf=True)
                    if not current:
                        return
                    db.execute("DELETE FROM sessions WHERE token_hash=?",(current["token_hash"],))
                    self.send_response(204)
                    secure = "; Secure" if os.environ.get("APP_ENV", "development").lower() == "production" else ""
                    self.send_header("Set-Cookie", f"{self.cookie_name()}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0{secure}")
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
                    if not self.allow_write(db, "inquiry", 10, 3600):
                        return self.send_json({"error": "Too many inquiries. Try again later."}, 429)
                    listing_id = str(payload.get("listingId", ""))
                    message = str(payload.get("message", "")).strip()
                    student_id = current["id"]
                    if len(message) < 8 or len(message) > 2000:
                        return self.send_json({"error": "Message must be between 8 and 2,000 characters."}, 400)
                    listing = db.execute("SELECT is_sample FROM listings WHERE id=? AND status='active'", (listing_id,)).fetchone()
                    if not listing:
                        return self.send_json({"error": "This listing is no longer available."}, 404)
                    if listing["is_sample"]:
                        return self.send_json({"error": "Sample listings are fictional and cannot receive inquiries."}, 400)
                    cursor = db.execute("INSERT INTO inquiries(listing_id,student_id,message) VALUES(?,?,?) RETURNING id", (listing_id, student_id, message))
                    inquiry_id = cursor.fetchone()[0]
                    owner = db.execute("SELECT o.email,o.name,l.title FROM listings l JOIN owners o ON o.id=l.owner_id WHERE l.id=?", (listing_id,)).fetchone()
                    renter = db.execute("SELECT name FROM accounts WHERE id=?", (student_id,)).fetchone()
                    if owner:
                        base_url=os.environ.get("ROOMROUTE_PUBLIC_URL","http://127.0.0.1:8765").rstrip("/")
                        queue_email(db,owner["email"],"New RoomRoute rental inquiry",f"Hello {owner['name']},\n\n{renter['name'] if renter else 'A renter'} sent an inquiry about {owner['title']}. Sign in to your RoomRoute account to view and reply.\n\n{base_url}/")
                    return self.send_json({"id": inquiry_id, "message": "Inquiry received. The owner has been notified by email."}, 201)
                if self.path == "/api/listings":
                    if not self.check_origin():
                        return self.send_json({"error": "Request origin could not be verified."}, 403)
                    current = self.require_session(db, role="owner", csrf=True)
                    if not current:
                        return
                    if not self.allow_write(db, "listing", 10, 3600):
                        return self.send_json({"error": "Too many listing changes. Try again later."}, 429)
                    title = str(payload.get("title", "")).strip()
                    kind = str(payload.get("type", ""))
                    area = str(payload.get("area", ""))
                    rent_value, deposit_value = payload.get("rent"), payload.get("deposit")
                    if type(rent_value) is not int or type(deposit_value) is not int:
                        return self.send_json({"error": "Rent and deposit must be whole numbers."}, 400)
                    rent, deposit = rent_value, deposit_value
                    furnishing = str(payload.get("furnishing", "Semi furnished"))
                    available_from = str(payload.get("availableFrom", ""))
                    summary = str(payload.get("summary", "")).strip()
                    try:
                        date.fromisoformat(available_from)
                        valid_date = len(available_from) == 10
                    except ValueError:
                        valid_date = False
                    if not title or len(title) > 100 or kind not in {"Private room", "Shared room", "1 BHK flat", "2 BHK flat"} or area not in AREAS or furnishing not in {"Fully furnished", "Semi furnished", "Unfurnished"} or rent < 1 or rent > 1000000 or deposit < 0 or deposit > 10000000 or not valid_date or len(summary) > 500 or type(payload.get("parking")) is not bool or type(payload.get("electricityIncluded")) is not bool:
                        return self.send_json({"error": "Enter a title, valid property type, Nagpur area, and realistic rent and deposit."}, 400)
                    new_id = f"RR-{secrets.token_hex(12)}"
                    db.execute("INSERT INTO listings(id,owner_id,title,type,rent,deposit,area,furnishing,parking,electricity_included,available_from,photo,summary,amenities,is_sample,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'pending')", (new_id, current["id"], title, kind, rent, deposit, area, furnishing, int(payload["parking"]), int(payload["electricityIncluded"]), available_from, "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1000&q=80", summary, json.dumps([])))
                    return self.send_json({"id": new_id, "status":"pending", "message": "Listing submitted for review. It will appear publicly after approval."}, 201)
                if path.startswith("/api/listings/") and path.endswith("/report"):
                    if not self.check_origin(): return self.send_json({"error":"Request origin could not be verified."},403)
                    current=self.require_session(db,csrf=True)
                    if not current: return
                    if not self.allow_write(db,"listing_report",10,3600): return self.send_json({"error":"Too many reports. Try again later."},429)
                    listing_id=path[len("/api/listings/"):-len("/report")].strip("/")
                    listing=db.execute("SELECT id,is_sample FROM listings WHERE id=?",(listing_id,)).fetchone()
                    reason=str(payload.get("reason","")); details=str(payload.get("details"," ")).strip()
                    if not listing or listing["is_sample"]: return self.send_json({"error":"This listing cannot be reported."},404)
                    if reason not in {"Misleading information","Already rented","Unsafe or discriminatory","Suspected scam","Other"} or len(details)>1000: return self.send_json({"error":"Choose a valid report reason and keep details under 1,000 characters."},400)
                    db.execute("INSERT INTO listing_reports(listing_id,reporter_id,reason,details) VALUES(?,?,?,?)",(listing_id,current["id"],reason,details))
                    return self.send_json({"message":"Report sent to RoomRoute moderation."},201)
                if path.startswith("/api/moderation/listings/"):
                    if not self.check_origin(): return self.send_json({"error":"Request origin could not be verified."},403)
                    current=self.require_session(db,role="moderator",csrf=True)
                    if not current: return
                    listing_id=path[len("/api/moderation/listings/"):]
                    action=str(payload.get("action","")); note=str(payload.get("note"," ")).strip()
                    if action not in {"approve","reject","pause"} or len(note)>1000: return self.send_json({"error":"Choose approve, reject, or pause and keep the note under 1,000 characters."},400)
                    status={"approve":"active","reject":"rejected","pause":"paused"}[action]
                    changed=db.execute("UPDATE listings SET status=?,moderation_note=? WHERE id=? AND is_sample=0",(status,note,listing_id)).rowcount
                    if not changed: return self.send_json({"error":"Listing not found."},404)
                    return self.send_json({"message":f"Listing {status}."})
                if path.startswith("/api/moderation/reports/"):
                    if not self.check_origin(): return self.send_json({"error":"Request origin could not be verified."},403)
                    current=self.require_session(db,role="moderator",csrf=True)
                    if not current: return
                    report_id=path[len("/api/moderation/reports/"):]
                    status=str(payload.get("status",""))
                    if status not in {"reviewed","dismissed"}: return self.send_json({"error":"Choose reviewed or dismissed."},400)
                    changed=db.execute("UPDATE listing_reports SET status=? WHERE id=? AND status='open'",(status,report_id)).rowcount
                    if not changed: return self.send_json({"error":"Open report not found."},404)
                    return self.send_json({"message":"Report updated."})
            self.send_json({"error": "Not found"}, 404)
        except sqlite3.IntegrityError:
            self.send_json({"error": "This record conflicts with existing data."}, 409)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": f"Invalid request: {exc}"}, 400)
        except Exception as exc:
            if str(getattr(exc,"sqlstate","")).startswith("23"):
                self.send_json({"error":"This record conflicts with existing data."},409)
                return
            if os.environ.get("APP_ENV", "development").lower() != "production":
                traceback.print_exc()
            self.send_json({"error": "The request could not be completed."}, 500)

    def log_message(self, fmt, *args):
        # Verification/reset tokens live in query strings; keep queries and client IPs out of logs.
        print(f"{self.log_date_time_string()} {self.command} {urlparse(self.path).path}")


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Bound concurrent request threads and read time to limit resource exhaustion."""
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, address, handler, max_workers=64):
        self._worker_slots=__import__("threading").BoundedSemaphore(max_workers)
        super().__init__(address,handler)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(15)
        return request, address

    def process_request(self, request, client_address):
        if not self._worker_slots.acquire(timeout=1):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self._worker_slots.release()


def validate_production_config():
    missing=[]
    if not IS_POSTGRES: missing.append("DATABASE_URL (PostgreSQL)")
    if not os.environ.get("REDIS_URL"): missing.append("REDIS_URL")
    if not os.environ.get("SMTP_HOST"): missing.append("SMTP_HOST")
    if not os.environ.get("SMTP_FROM"): missing.append("SMTP_FROM")
    if os.environ.get("SMTP_STARTTLS", "1") != "1": missing.append("SMTP_STARTTLS=1")
    if os.environ.get("SMTP_USERNAME") and not os.environ.get("SMTP_PASSWORD"): missing.append("SMTP_PASSWORD")
    public_url=urlparse(os.environ.get("ROOMROUTE_PUBLIC_URL",""))
    if public_url.scheme!="https" or not public_url.hostname: missing.append("ROOMROUTE_PUBLIC_URL (HTTPS)")
    if not os.environ.get("ROOMROUTE_ALLOWED_HOSTS"): missing.append("ROOMROUTE_ALLOWED_HOSTS")
    if missing: raise SystemExit("Production startup refused. Configure: " + ", ".join(missing))
    try:
        port=int(os.environ.get("SMTP_PORT","587"))
        if not 1<=port<=65535: raise ValueError
        pool_size=int(os.environ.get("ROOMROUTE_DB_POOL_SIZE","20"))
        if not 1<=pool_size<=64: raise ValueError
    except ValueError as exc:
        raise SystemExit("Production startup refused. SMTP_PORT and ROOMROUTE_DB_POOL_SIZE must be valid numeric values.") from exc
    hosts=[value.strip() for value in os.environ["ROOMROUTE_ALLOWED_HOSTS"].split(",") if value.strip()]
    parsed_hosts=[urlparse("//"+value) for value in hosts]
    try:
        invalid_host=not hosts or any(parsed.hostname is None or parsed.port is not None or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password for parsed in parsed_hosts)
    except ValueError:
        invalid_host=True
    if invalid_host:
        raise SystemExit("Production startup refused. ROOMROUTE_ALLOWED_HOSTS must contain bare hostnames.")
    redis_url=urlparse(os.environ["REDIS_URL"])
    if redis_url.scheme not in {"redis","rediss"} or not redis_url.hostname:
        raise SystemExit("Production startup refused. REDIS_URL must be a valid Redis URL.")
    for value in os.environ.get("ROOMROUTE_TRUST_PROXY_CIDRS","").split(","):
        if value.strip():
            try: ipaddress.ip_network(value.strip(),strict=False)
            except ValueError as exc: raise SystemExit("Production startup refused. ROOMROUTE_TRUST_PROXY_CIDRS contains an invalid network.") from exc


def outbox_worker():
    while True:
        try:
            with db_session() as db: deliver_pending_email(db)
        except Exception as exc:
            print(f"Email delivery worker unavailable: {type(exc).__name__}")
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run or manage the RoomRoute local preview")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--seed-sample-data", action="store_true", help="Add clearly tagged sample owners, listings, and renter profiles")
    action.add_argument("--remove-sample-data", action="store_true", help="Delete sample inquiries, listings, owners, and renter profiles")
    action.add_argument("--create-moderator", action="store_true", help="Create an initial moderation account interactively")
    args = parser.parse_args()
    init_db()
    if args.create_moderator:
        import getpass
        email=input("Moderator email: ").strip().lower()
        name=input("Moderator name: ").strip()
        password=getpass.getpass("Moderator password (12+ characters): ")
        if not EMAIL_RE.fullmatch(email) or not 2<=len(name)<=80 or not 12<=len(password)<=256:
            raise SystemExit("Provide a valid email, name, and password of at least 12 characters.")
        with db_session() as db:
            existing=db.execute("SELECT 1 FROM accounts WHERE email=?",(email,)).fetchone()
            if existing: raise SystemExit("An account with that email already exists.")
            db.execute("INSERT INTO accounts(id,email,name,role,password_hash,is_verified) VALUES(?,?,?,?,?,1)",(f"MOD-{secrets.token_hex(12)}",email,name,"moderator",PASSWORD_HASHER.hash(password)))
        print("Moderator account created. Keep the credentials in your password manager.")
        raise SystemExit(0)
    if args.seed_sample_data:
        print("Sample data loaded." if seed_sample_data() else "Sample data is already loaded; no records changed.")
        raise SystemExit(0)
    if args.remove_sample_data:
        remove_sample_data()
        print("Sample records removed. User-created non-sample records were retained.")
        raise SystemExit(0)
    production=os.environ.get("APP_ENV", "development").lower() == "production"
    if production:
        validate_production_config()
    host = os.environ.get("ROOMROUTE_HOST", "0.0.0.0" if production else "127.0.0.1")
    port = int(os.environ.get("ROOMROUTE_PORT", os.environ.get("PORT", "8765")))
    if not production and host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("ROOMROUTE_CONTAINER") != "1":
        raise SystemExit("This preview server is local-only and refuses non-loopback bind addresses.")
    if os.environ.get("ROOMROUTE_SEED_DATA", "0") == "1":
        print("Sample data loaded." if seed_sample_data() else "Sample data already present.")
    server = BoundedThreadingHTTPServer((host, port), Handler)
    import threading
    threading.Thread(target=outbox_worker,daemon=True,name="roomroute-email-outbox").start()
    print(f"RoomRoute {'production service' if production else 'local preview'} listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRoomRoute stopped.")

