"""Build the RoomRoute DBMS mini-project report in the supplied 21-page order.

Run from the repository root with: python docs/reports/build_report.py
Requires reportlab. All people, properties and figures in the report are
synthetic local-preview records unless stated otherwise.
"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, NextPageTemplate,
    Table, TableStyle, Preformatted, Flowable, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "RoomRoute_DBMS_Mini_Project_Report.pdf"
W, H = A4
INK = colors.HexColor("#1c2820")
GREEN = colors.HexColor("#315b43")
PALE = colors.HexColor("#eff3ed")
GOLD = colors.HexColor("#c99d4b")
MUTED = colors.HexColor("#657168")
SAMPLE = colors.HexColor("#fff2cf")

# Arial is embedded to keep the rupee sign and other report glyphs legible.
pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", r"C:\Windows\Fonts\ariali.ttf"))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="RRTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=INK, alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle(name="RRH1", parent=styles["Heading1"], fontName="Arial-Bold", fontSize=16, leading=20, textColor=GREEN, spaceBefore=3, spaceAfter=10, keepWithNext=True))
styles.add(ParagraphStyle(name="RRH2", parent=styles["Heading2"], fontName="Arial-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=9, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name="RRBody", parent=styles["BodyText"], fontName="Arial", fontSize=9.5, leading=13.2, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name="RRSmall", parent=styles["BodyText"], fontName="Arial", fontSize=8.5, leading=11.4, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="RRNote", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=10.5, textColor=colors.HexColor("#684a13"), backColor=SAMPLE, borderPadding=7, spaceBefore=4, spaceAfter=7))
styles.add(ParagraphStyle(name="RRNoteInner", parent=styles["BodyText"], fontName="Arial-Bold", fontSize=8.5, leading=11.4, textColor=colors.HexColor("#684a13"), backColor=SAMPLE, borderPadding=8, spaceBefore=5, spaceAfter=8))
styles.add(ParagraphStyle(name="RRCode", fontName="Courier", fontSize=7.6, leading=9.4, textColor=INK, leftIndent=6, rightIndent=6, borderColor=colors.HexColor("#dfe6df"), borderWidth=.6, borderPadding=8, backColor=colors.HexColor("#f7f9f7"), spaceBefore=4, spaceAfter=8))
styles.add(ParagraphStyle(name="RRCenter", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=INK, alignment=TA_CENTER, spaceAfter=8))
styles.add(ParagraphStyle(name="RRCell", parent=styles["BodyText"], fontName="Arial", fontSize=8.3, leading=11.2, textColor=INK))
styles.add(ParagraphStyle(name="RRCellHead", parent=styles["BodyText"], fontName="Arial-Bold", fontSize=8.3, leading=11.2, textColor=GREEN))


def para(text, style="RRBody"):
    return Paragraph(text, styles[style])


def code(text):
    return Preformatted(text.strip(), styles["RRCode"])


def grid(rows, widths=None, header=True, font=7.4):
    cooked = [[para(str(v), "RRCellHead" if header and rid == 0 else "RRCell") for v in row] for rid, row in enumerate(rows)]
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#cbd5cc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), PALE), ("TEXTCOLOR", (0, 0), (-1, 0), GREEN)]
    t.setStyle(TableStyle(cmds))
    return t


class InterfacePanel(Flowable):
    """A labeled vector interface illustration, not a browser screenshot."""
    def __init__(self, variant, width=180*mm, height=210*mm):
        super().__init__()
        self.variant, self.width, self.height = variant, width, height

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(colors.HexColor("#f6f8f4")); c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setFillColor(colors.white); c.roundRect(5*mm, h-21*mm, w-10*mm, 13*mm, 5, fill=1, stroke=0)
        c.setFillColor(GREEN); c.circle(14*mm, h-14.5*mm, 4*mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 8); c.drawCentredString(14*mm, h-17*mm, "R")
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 11); c.drawString(21*mm, h-16*mm, "roomroute")
        c.setFont("Helvetica", 7); c.drawRightString(w-11*mm, h-16*mm, "Nagpur  ·  Saved  ·  List a place")
        c.setFillColor(SAMPLE); c.roundRect(8*mm, h-30*mm, w-16*mm, 6*mm, 3, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#684a13")); c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(w/2, h-28*mm, "LOCAL PREVIEW · FICTIONAL DATA · NOT A LIVE RENTAL SERVICE")
        if self.variant == 1:
            c.setFillColor(INK); c.setFont("Arial-Bold", 20); c.drawString(10*mm, h-48*mm, "A place to land.")
            c.setFillColor(GREEN); c.setFont("Arial-Italic", 19); c.drawString(10*mm, h-57*mm, "A city to grow.")
            c.setFillColor(MUTED); c.setFont("Arial", 8); c.drawString(10*mm, h-65*mm, "Find a room or flat that fits your life and budget.")
            labels = [("AREA", "All Nagpur"), ("PLACE TYPE", "Rooms & flats"), ("MONTHLY BUDGET", "Any budget")]
            x = 10*mm
            for title, value in labels:
                c.setFillColor(colors.white); c.roundRect(x, h-84*mm, 43*mm, 14*mm, 4, fill=1, stroke=0)
                c.setFillColor(MUTED); c.setFont("Arial-Bold", 6); c.drawString(x+3*mm, h-75*mm, title)
                c.setFillColor(INK); c.setFont("Arial", 8); c.drawString(x+3*mm, h-81*mm, value)
                x += 46*mm
            c.setFillColor(GREEN); c.roundRect(x, h-84*mm, 28*mm, 14*mm, 4, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Arial-Bold", 7); c.drawCentredString(x+14*mm, h-78*mm, "Find a place")
            c.setFillColor(INK); c.setFont("Arial-Bold", 12); c.drawString(10*mm, h-101*mm, "Places to call home")
            self._cards(c, w, h-108*mm, 3)
        elif self.variant == 2:
            c.setFillColor(INK); c.setFont("Arial-Bold", 15); c.drawString(10*mm, h-48*mm, "Filter the details that matter")
            self._cards(c, w, h-60*mm, 2)
            c.setFillColor(colors.white); c.roundRect(10*mm, 13*mm, w-20*mm, 51*mm, 6, fill=1, stroke=0)
            c.setFillColor(GREEN); c.setFont("Arial-Bold", 11); c.drawString(16*mm, 54*mm, "Bright room near VNIT")
            c.setFillColor(MUTED); c.setFont("Arial", 8); c.drawString(16*mm, 46*mm, "Dharampeth, Nagpur  ·  Private room")
            c.setFillColor(INK); c.setFont("Arial-Bold", 10); c.drawString(16*mm, 35*mm, "₹8,500 / month   ·   Deposit ₹17,000")
            for i, s in enumerate(["Electricity billed separately", "Parking available", "Owner photos not provided"]):
                c.setFillColor(MUTED); c.setFont("Arial", 7); c.drawString(16*mm, 27*mm-i*5*mm, "•  "+s)
        else:
            c.setFillColor(INK); c.setFont("Arial-Bold", 15); c.drawString(10*mm, h-48*mm, "Owner workspace and listing review")
            for i, (title, sub, status) in enumerate([
                ("Your submitted place", "Rent, deposit, area, utilities", "PENDING REVIEW"),
                ("Listing availability", "Pause an active listing", "OWNER ACTION"),
                ("Safety reports", "Moderator review queue", "STAFF ONLY"),
            ]):
                y = h-(65+i*38)*mm
                c.setFillColor(colors.white); c.roundRect(10*mm, y, w-20*mm, 29*mm, 5, fill=1, stroke=0)
                c.setFillColor(INK); c.setFont("Arial-Bold", 10); c.drawString(16*mm, y+19*mm, title)
                c.setFillColor(MUTED); c.setFont("Arial", 7.5); c.drawString(16*mm, y+10*mm, sub)
                c.setFillColor(GREEN); c.setFont("Arial-Bold", 7); c.drawRightString(w-15*mm, y+19*mm, status)
            c.setFillColor(SAMPLE); c.roundRect(10*mm, 18*mm, w-20*mm, 17*mm, 4, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#684a13")); c.setFont("Arial-Bold", 7)
            c.drawString(15*mm, 28*mm, "Registration, verification and inquiry flows require a configured email provider.")
        c.setFillColor(MUTED); c.setFont("Arial-Italic", 7)
        c.drawCentredString(w/2, 5*mm, "Illustrative screen layout based on the current frontend source; not a production capture.")

    def _cards(self, c, w, top, count):
        gap = 5*mm; left = 10*mm; cardw = (w-20*mm-(count-1)*gap)/count
        for i in range(count):
            x = left+i*(cardw+gap); y = top-75*mm
            c.setFillColor(colors.white); c.roundRect(x, y, cardw, 73*mm, 5, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#e8eee8")); c.roundRect(x+3*mm, y+42*mm, cardw-6*mm, 27*mm, 4, fill=1, stroke=0)
            c.setFillColor(MUTED); c.setFont("Arial", 7); c.drawCentredString(x+cardw/2, y+54*mm, "Owner photos not provided")
            c.setFillColor(GREEN); c.setFont("Arial-Bold", 8)
            c.drawString(x+3*mm, y+36*mm, ["Bright room near VNIT", "Quiet 1 BHK flat", "Shared student room"][i%3])
            c.setFillColor(MUTED); c.setFont("Arial", 6.6); c.drawString(x+3*mm, y+29*mm, ["Dharampeth", "Laxmi Nagar", "Pratap Nagar"][i%3]+", Nagpur")
            c.setFillColor(INK); c.setFont("Arial-Bold", 9); c.drawString(x+3*mm, y+19*mm, ["₹8,500", "₹13,000", "₹5,500"][i%3]+" / mo")
            c.setFillColor(MUTED); c.setFont("Arial", 6.5); c.drawString(x+3*mm, y+10*mm, "Sample · electricity details shown")


def draw_page(canvas, doc):
    n = canvas.getPageNumber()
    if n == 1:
        canvas.setStrokeColor(GREEN); canvas.setLineWidth(1.2); canvas.line(28*mm, 41*mm, W-28*mm, 41*mm)
        canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 8); canvas.drawCentredString(W/2, 16*mm, "Prepared 22 October 2026  ·  Nagpur, Maharashtra")
    else:
        canvas.setStrokeColor(colors.HexColor("#dfe5df")); canvas.line(20*mm, H-18*mm, W-20*mm, H-18*mm)
        canvas.setFillColor(GREEN); canvas.setFont("Helvetica-Bold", 8); canvas.drawString(20*mm, H-14*mm, "ROOMROUTE  /  DATABASE MANAGEMENT SYSTEM")
        canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 8); canvas.drawRightString(W-20*mm, 13*mm, f"Page {n}")


doc = BaseDocTemplate(str(OUT), pagesize=A4, leftMargin=21*mm, rightMargin=21*mm, topMargin=24*mm, bottomMargin=20*mm, title="RoomRoute DBMS Mini Project Report", author="Tanay Gaykwad")
cover_frame = Frame(21*mm, 20*mm, W-42*mm, H-44*mm, id="cover", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
content_frame = Frame(15*mm, 18*mm, W-30*mm, H-41*mm, id="content", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([
    PageTemplate(id="cover", frames=[cover_frame], onPage=draw_page),
    PageTemplate(id="content", frames=[content_frame], onPage=draw_page),
])
story = []

# Page 1 — cover
story += [Spacer(1, 35*mm), para("DATABASE MANAGEMENT SYSTEM", "RRTitle"), para("MINI PROJECT REPORT", "RRTitle"), Spacer(1, 7*mm), para("ROOMROUTE", "RRTitle"), para("Nagpur Rental Search and Listing Platform", "RRCenter"), Spacer(1, 13*mm), para("DBMS PROJECT · POSTGRESQL / SQLITE PREVIEW", "RRCenter"), Spacer(1, 18*mm), para("Prepared by: Tanay Gaykwad", "RRCenter"), para("College / department: ______________________________", "RRCenter"), para("Roll number: _____________________________________", "RRCenter"), Spacer(1, 12*mm), para("Repository link: https://github.com/tanay-gaykwad/roomroute", "RRCenter"), para("Live application: Not deployed", "RRCenter"), Spacer(1, 13*mm), para("This report documents the current code and local synthetic preview. It does not claim that fictional records are real rentals or that a public service is live.", "RRNote"), NextPageTemplate("content"), PageBreak()]

# Page 2 — index
story += [para("INDEX", "RRH1"), grid([["Sr.", "Contents", "Page"], ["1", "Project Structure / 20-Step Sequence", "3"], ["2", "Aim, Objectives, Theory & Requirements", "4"], ["3", "Original PostgreSQL Code", "5–11"], ["4", "Basic SQL Query Outputs", "12"], ["5", "JOIN Outputs", "13"], ["6", "Aggregate Functions, GROUP BY & Subquery", "14"], ["7", "Indexes and database behavior", "15"], ["8", "CRUD — Create & Read", "16"], ["9", "CRUD — Update & Delete", "17"], ["10", "Frontend interface illustrations", "18–20"], ["11", "Result & Conclusion", "21"], ["12", "Advantages, Disadvantages & Future Scope", "21"]], [20*mm, 136*mm, 24*mm]), Spacer(1, 8*mm), para("PROJECT AT A GLANCE", "RRH2"), grid([["Item", "Project detail"], ["Service area", "Nagpur, Maharashtra"], ["Core records", "Owners, renter profiles, accounts, listings, inquiries and moderation reports"], ["Database modes", "PostgreSQL for configured service mode; SQLite for local preview"], ["Preview inventory", "50 synthetic owners, 200 renter profiles and 50 synthetic room/flat listings"]], [43*mm, 137*mm]), Spacer(1, 4*mm), para("Reading note: the report preserves the supplied college report's section order. SQL and outputs are adapted to RoomRoute; no View, Trigger, live website, real user account or actual rental is claimed.", "RRNoteInner"), PageBreak()]

# Page 3
steps = [["Step", "Module"], ["1", "Create owner and renter profile tables"], ["2", "Create account and role table"], ["3", "Create verified-session table"], ["4", "Create one-time authentication-token table"], ["5", "Create rental listing table"], ["6", "Create inquiry table"], ["7", "Create moderation report table"], ["8", "Create durable email outbox table"], ["9", "Create authentication-attempt records"], ["10", "Create indexes and schema migration version"], ["11", "Load synthetic preview owners and renters"], ["12", "Load synthetic preview room and flat listings"], ["13", "Run basic filter and sort queries"], ["14", "Join listings to owners"], ["15", "Aggregate listing and inquiry counts"], ["16", "Group by area and property type"], ["17", "Use bounded listing pagination"], ["18", "Create an owner listing (CRUD)"], ["19", "Approve, pause, report and export records"], ["20", "Review frontend and local service flows"]]
story += [para("PROJECT STRUCTURE / 20-STEP SEQUENCE", "RRH1"), grid(steps, [20*mm, 160*mm]), Spacer(1, 6*mm), para("WORK PHASES", "RRH2"), grid([["Phase", "Steps", "Outcome"], ["Schema and safety foundations", "1–10", "Relational tables, constraints, indexes and migrations"], ["Database analysis", "11–17", "Synthetic fixtures, filtered search, joins and aggregate queries"], ["Application workflows", "18–20", "Owner listing lifecycle, renter discovery and moderation review"]], [45*mm, 23*mm, 112*mm]), PageBreak()]

# Page 4
story += [para("1. AIM", "RRH1"), para("To design and implement RoomRoute, a Nagpur-focused rental search platform that models owners, renters, accounts, room and flat listings, inquiries, and moderation using relational database operations.", "RRBody"), para("2. OBJECTIVES", "RRH2"), para("• Store owner, renter, account, listing, inquiry and moderation data with relational keys. • Search rooms and flats using location, budget, utilities, furnishing and parking. • Apply authentication, verification, inquiry, listing review and privacy workflows. • Demonstrate filtering, joins, aggregation, indexes and CRUD with synthetic preview data.", "RRBody"), para("3. THEORY", "RRH2"), para("A relational database organizes records into tables and links them with primary and foreign keys. Constraints preserve valid relationships; indexes support common lookups; SQL performs filtering, joins, grouping and updates. RoomRoute uses PostgreSQL in configured service mode and SQLite for local preview. Synthetic records are explicitly separated from registered accounts and real user submissions.", "RRBody"), para("4. SOFTWARE & HARDWARE REQUIREMENTS", "RRH2"), grid([["Category", "Requirement"], ["Software", "Python 3.12+, PostgreSQL, Redis, modern browser; Docker Compose for local multi-service preview"], ["Libraries", "argon2-cffi, psycopg with pool support, redis-py"], ["Hardware", "Development computer with internet for package setup; deployment resources must be selected and load-tested"], ["Current evidence", "Local preview database contains 50 synthetic owners, 200 synthetic renter profiles and 50 synthetic listings; no account or inquiry rows"]], [43*mm, 137*mm]), Spacer(1, 7*mm), para("RELATIONAL LINKS", "RRH2"), grid([["Parent record", "Relationship", "Dependent record"], ["owners.id", "One owner to many properties", "listings.owner_id"], ["listings.id", "One property to many inquiries", "inquiries.listing_id"], ["accounts.id", "One account to many sessions / tokens", "sessions.account_id / auth_tokens.account_id"], ["accounts.id", "One reporter to many safety reports", "listing_reports.reporter_id"]], [39*mm, 75*mm, 66*mm]), PageBreak()]

# Pages 5–11: implementation extracts, not falsely a MySQL dump
story += [para("5. ORIGINAL POSTGRESQL CODE — ACCOUNTS AND AUTHENTICATION", "RRH1"), para("RoomRoute's schema is created through additive migrations in server.py. The snippets below summarize the current PostgreSQL table definitions.", "RRSmall"), code("""CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK
    (role IN ('owner','student','employee','moderator')),
  password_hash TEXT NOT NULL,
  is_verified INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE auth_tokens (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL CHECK (purpose IN ('verify','reset')),
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ
);"""), para("Passwords are stored as Argon2 hashes. Session tokens are random; only their digest is stored. Verification and reset tokens are hashed, expiring and single use.", "RRBody"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — OWNER, RENTER AND LISTING TABLES", "RRH1"), code("""CREATE TABLE owners (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'owner',
  is_sample INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
  occupation TEXT NOT NULL, budget INTEGER NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE listings (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES owners(id),
  title TEXT NOT NULL, type TEXT NOT NULL,
  rent INTEGER NOT NULL, deposit INTEGER NOT NULL,
  area TEXT NOT NULL, city TEXT NOT NULL DEFAULT 'Nagpur',
  furnishing TEXT NOT NULL, parking INTEGER NOT NULL,
  electricity_included INTEGER NOT NULL,
  available_from TEXT NOT NULL, photo TEXT NOT NULL,
  summary TEXT NOT NULL, amenities TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  is_sample INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);"""), para("Foreign keys link listings to owners. New real listings start in pending review; only active records appear in public search. Real listings have no photo upload yet.", "RRBody"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — INQUIRIES AND MODERATION", "RRH1"), code("""CREATE TABLE inquiries (
  id BIGSERIAL PRIMARY KEY,
  listing_id TEXT NOT NULL REFERENCES listings(id),
  student_id TEXT NOT NULL REFERENCES users(id),
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE listing_reports (
  id BIGSERIAL PRIMARY KEY,
  listing_id TEXT NOT NULL REFERENCES listings(id),
  reporter_id TEXT NOT NULL REFERENCES accounts(id),
  reason TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE email_outbox (
  id BIGSERIAL PRIMARY KEY,
  recipient TEXT NOT NULL, subject TEXT NOT NULL,
  body TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at TIMESTAMPTZ, last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);"""), para("Inquiry delivery is queued in the database and requires a configured SMTP provider in service mode. The local preview can print verification links to its terminal when email is not configured.", "RRBody")]
story += [para("5. ORIGINAL POSTGRESQL CODE — SYNTHETIC PREVIEW DATA", "RRH1"), code("""# Local-only operator command; idempotent and removable.
python server.py --seed-sample-data

# Remove only tagged synthetic records.
python server.py --remove-sample-data

# Production startup refuses these sample-data operations.
"""), para("The repository's local SQLite fixture currently has 50 owners, 200 renter profiles and 50 listings. These records have no account credentials and sample listings cannot receive inquiries.", "RRBody"), para("This project does not include an SQL seed dump. The fixture is generated by the application's explicit seed command, and production startup blocks seeding. This prevents a fictitious marketing claim that the example profiles are real owners or renters.", "RRNote"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — BASIC SQL AND JOIN", "RRH1"), para("Examples use bound parameters in application code; values below illustrate direct database analysis.", "RRSmall"), code("""-- Public listings within a budget
SELECT id, title, type, area, rent, furnishing
FROM listings
WHERE status = 'active' AND is_sample = 1
  AND rent <= 12000
ORDER BY rent ASC, created_at DESC
LIMIT 50 OFFSET 0;

-- Listing with owner display name
SELECT l.title, l.area, l.rent, o.name AS owner_name
FROM listings AS l
JOIN owners AS o ON o.id = l.owner_id
WHERE l.status = 'active'
ORDER BY l.created_at DESC;

-- Inquiries linked to their listing
SELECT l.title, i.status, i.created_at
FROM inquiries AS i
JOIN listings AS l ON l.id = i.listing_id;"""), para("Public listing search applies filters in the database and caps each response at 100 records. Owners are scoped to the selected page; the browser can request more results with pagination.", "RRBody"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — AGGREGATES AND GROUPING", "RRH1"), code("""SELECT COUNT(*) AS listing_count
FROM listings WHERE is_sample = 1;

SELECT area, COUNT(*) AS places,
       MIN(rent) AS lowest_rent,
       ROUND(AVG(rent)) AS average_rent
FROM listings
WHERE is_sample = 1
GROUP BY area
HAVING COUNT(*) >= 2
ORDER BY area;

SELECT type, COUNT(*) AS places
FROM listings WHERE is_sample = 1
GROUP BY type ORDER BY places DESC;

-- A bounded sample of premium listings
SELECT title, rent FROM listings
WHERE is_sample = 1
  AND rent > (SELECT AVG(rent) FROM listings WHERE is_sample = 1)
ORDER BY rent DESC LIMIT 5;"""), para("These queries are suitable for analyzing the synthetic preview inventory. They are not a rating or review system: student reviews of owners and properties are not implemented.", "RRBody"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — INDEXES AND MIGRATIONS", "RRH1"), code("""CREATE INDEX IF NOT EXISTS idx_listings_public_order
  ON listings(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_public_area
  ON listings(status, area, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_public_rent
  ON listings(status, rent);
CREATE INDEX IF NOT EXISTS idx_inquiries_listing_order
  ON inquiries(listing_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status
  ON listing_reports(status, created_at);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);"""), para("The supplied college format requests a View and Trigger exercise. RoomRoute currently relies on parameterized queries and explicit application flows; it has no database View or Trigger. This report does not claim those objects exist.", "RRNote"), PageBreak()]
story += [para("5. ORIGINAL POSTGRESQL CODE — CRUD OPERATIONS", "RRH1"), code("""-- CREATE: owner-submitted real listings start pending
INSERT INTO listings
  (id, owner_id, title, type, rent, deposit, area,
   furnishing, parking, electricity_included,
   available_from, photo, summary, amenities, status,
   is_sample)
VALUES
  (:id, :owner_id, :title, :type, :rent, :deposit, :area,
   :furnishing, :parking, :electricity_included,
   :available_from, '', :summary, '[]', 'pending', 0);

-- READ: active public listings only
SELECT id, title, rent, area FROM listings
WHERE status='active' ORDER BY created_at DESC;

-- UPDATE: owner withdraws an active listing
UPDATE listings SET status='paused'
WHERE id=:listing_id AND owner_id=:owner_id
  AND is_sample=0 AND status='active';

-- DELETE: privacy action removes linked account data
-- Performed in a transaction after password verification."""), para("The live service requires PostgreSQL and Redis. A local SQLite database is used only for development and demonstration.", "RRBody"), PageBreak()]

# Pages 12–17 output examples
story += [para("6. OUTPUT — BASIC SQL QUERIES", "RRH1"), grid([["Local preview table", "Records"], ["Owners (synthetic)", "50"], ["Renter profiles (synthetic)", "200"], ["Listings (synthetic)", "50"], ["Accounts", "0"], ["Inquiries", "0"]], [98*mm, 60*mm]), Spacer(1, 8*mm), para("Representative query: SELECT COUNT(*) FROM listings WHERE is_sample = 1; returns 50 for the checked local fixture. Sample identities and listings are fictional and cannot be contacted through the inquiry feature.", "RRBody"), para("Example budget search returns listings meeting the selected maximum rent after area and property-type filters. Public responses are capped at 100 rows per page.", "RRNote"), PageBreak()]
story += [para("7. OUTPUT — JOIN QUERIES", "RRH1"), grid([["Joined field", "Relationship"], ["Listing title and owner name", "listings.owner_id → owners.id"], ["Inquiry and place title", "inquiries.listing_id → listings.id"], ["Moderation report and reporter", "listing_reports.reporter_id → accounts.id"]], [73*mm, 85*mm]), Spacer(1, 8*mm), para("Current preview listings join to 50 synthetic owner rows. The current fixture has no inquiries or platform accounts, so the inquiry and report joins return zero rows until actual verified users submit data.", "RRBody"), code("""SELECT l.title, o.name, l.area, l.rent
FROM listings l
INNER JOIN owners o ON o.id=l.owner_id
WHERE l.is_sample=1
ORDER BY l.area, l.rent
LIMIT 5;"""), PageBreak()]
story += [para("8. OUTPUT — AGGREGATES, GROUPING AND SUBQUERY", "RRH1"), grid([["Metric from local sample fixture", "Result"], ["Synthetic listings", "50"], ["Synthetic owners", "50"], ["Synthetic renter profiles", "200"], ["Active account records", "0"], ["Submitted inquiries", "0"]], [104*mm, 54*mm]), Spacer(1, 8*mm), para("Use GROUP BY area or type to compare inventory counts and rent ranges. A subquery can select listings above the preview's average rent. Results describe only the fictional local seed data and are not evidence of market availability or demand.", "RRBody"), grid([["Sample area", "Listings", "Rent span / month"], ["Bajaj Nagar", "5", "₹8,500–₹10,500"], ["Civil Lines", "5", "₹25,000–₹27,000"], ["Dharampeth", "5", "₹10,500–₹12,500"], ["Laxmi Nagar", "5", "₹22,000–₹24,000"], ["Manish Nagar", "5", "₹15,500–₹17,500"], ["Pratap Nagar", "5", "₹6,000–₹8,000"], ["Ramdaspeth", "5", "₹9,000–₹11,000"], ["Sadar", "5", "₹5,500–₹7,500"], ["Trimurti Nagar", "5", "₹12,000–₹14,000"], ["Wardha Road", "5", "₹14,500–₹16,500"]], [53*mm, 25*mm, 80*mm]), PageBreak()]
story += [para("9. OUTPUT — INDEXES, VIEW AND TRIGGER", "RRH1"), para("Indexes present in the application schema support public listing order, area and rent filtering, inquiry lookups, session expiry, authentication attempts, pending email and moderation reports.", "RRBody"), grid([["Database object", "Current project status"], ["idx_listings_public_order", "Implemented"], ["idx_listings_public_area", "Implemented"], ["idx_listings_public_rent", "Implemented"], ["idx_inquiries_listing_order", "Implemented"], ["Student-facing Review View", "Not implemented"], ["Database trigger", "Not implemented"]], [87*mm, 71*mm]), Spacer(1, 5*mm), para("The app currently has no verified student review feature. It would be unsafe to publish unverified accusations about owners; a future review feature needs verified tenancy and dispute handling.", "RRNoteInner"), PageBreak()]
story += [para("10. CRUD OUTPUT — CREATE AND READ", "RRH1"), para("Owner submission is saved as a pending real listing. Public search only returns records approved by a moderator and marked active.", "RRBody"), grid([["Operation", "Illustrative result"], ["CREATE listing", "Saved with status = pending"], ["READ owner workspace", "Owner sees their pending listing"], ["READ public catalogue", "Pending listing is hidden"], ["READ sample listing", "Clearly marked; inquiry disabled"]], [55*mm, 103*mm]), para("This is an application-flow result. The report does not create records in the owner's database.", "RRNote"), PageBreak()]
story += [para("11. CRUD OUTPUT — UPDATE AND DELETE", "RRH1"), grid([["Operation", "Behavior"], ["UPDATE availability", "Owner pauses an active real listing"], ["Relist", "Listing returns to moderation queue"], ["DELETE account", "Password verified; linked records removed"], ["Export account", "Authenticated account can download its data"]], [55*mm, 103*mm]), Spacer(1, 8*mm), para("Sample listings cannot be modified through the owner workspace. Account deletion and export endpoints exist, but a complete privacy program still requires operator policies, retention rules and tested backups.", "RRBody"), PageBreak()]

# Pages 18–20 visual illustrations, transparently marked
story += [para("12. FRONTEND APP / WEBPAGE — SEARCH AND DISCOVERY", "RRH1"), para("The frontend is responsive HTML, CSS and JavaScript. Search controls expose Nagpur area, property type and monthly budget. Sample inventory is labeled, and owner photos are not fabricated for real listings.", "RRSmall"), InterfacePanel(1), PageBreak()]
story += [para("12. FRONTEND APP / WEBPAGE — LISTING DETAILS", "RRH1"), para("Property cards show rent, deposit context, location, furnishing, parking and electricity details. These report illustrations follow the current frontend source and sample fixture; they are not screenshots captured from a live service.", "RRSmall"), InterfacePanel(2), PageBreak()]
story += [para("12. FRONTEND APP / WEBPAGE — OWNER AND REVIEW FLOWS", "RRH1"), para("Real owner submissions require email verification and moderation before they are public. The current service does not provide property identity checks, photo upload, or editing all listing fields after submission.", "RRSmall"), InterfacePanel(3), PageBreak()]

# Page 21
story += [para("13. RESULT", "RRH1"), para("RoomRoute has a working local-preview web interface and Python backend. The repository implements relational data access, synthetic records, filtering, bounded public listing pages, authenticated account flows, email-verification and password-reset token handling, inquiry storage and notification queue, listing moderation, reports, and account export/deletion routes. The current local fixture contains 50 sample owners, 200 sample renter profiles, and 50 sample listings.", "RRBody"), para("14. CONCLUSION", "RRH2"), para("The project demonstrates how relational databases support a rental discovery workflow. A code-level production mode uses PostgreSQL and shared Redis, but the service is not deployed and has not completed an independent penetration test or live restore test. A free ephemeral deployment is not suitable for real account data.", "RRBody"), para("15. ADVANTAGES", "RRH2"), para("• Combines room and flat search. • Filters by budget and practical property details. • Labels synthetic inventory. • Uses password hashing, email verification, CSRF protections, shared throttling, moderation and privacy endpoints. • Includes Docker Compose and automated CI configuration.", "RRSmall"), para("16. DISADVANTAGES / REMAINING WORK", "RRH2"), para("• No public deployment, real listing inventory or provider credentials. • No moderator MFA, owner/property verification, photo upload, listing edit, or student review system. • No measured capacity claim; pagination and load testing remain for private inboxes and reports. • Policies, backups, monitoring, restore drills and independent security review are still needed.", "RRSmall"), para("17. FUTURE SCOPE", "RRH2"), para("Add provider-backed image storage, owner verification, moderator MFA, pagination and retention for private records, verified tenancy reviews with dispute controls, AI-assisted search after privacy and quality assessment, and monitored production infrastructure with tested backups.", "RRSmall"), para("Repository: https://github.com/tanay-gaykwad/roomroute   |   Live application: Not deployed", "RRNote"), para("Status reviewed on 22 October 2026. Synthetic data is for interface and database exercises only.", "RRSmall")]

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.build(story)
print(OUT)
