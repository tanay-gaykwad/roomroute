# RoomRoute

[![CI](https://github.com/tanay-gaykwad/roomroute/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tanay-gaykwad/roomroute/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Find a room, flat, PG, or roommate in Nagpur with the costs and details visible before you arrange a visit.**

RoomRoute is an independent, open-source rental discovery project focused on students and working professionals around Lokmanya Nagar and Hingna, Nagpur, Maharashtra. This repository is a working prototype for that service.

> **Status:** There is no hosted public service or verified live inventory yet. The sample listings and profiles are fictional and clearly labeled. Do not use the preview to make rental or payment decisions.

## What it does

- Search rooms, flats, PG accommodation, and roommate listings by area, rent, setup, utilities, parking, accessibility, pets, student eligibility, laundry, and air conditioning.
- Compare owner-stated rent basis, deposit, maintenance, electricity, amenities, and photos.
- Save places locally, send inquiries, and continue owner-renter conversations after email verification.
- Opt into roommate introductions; contact details are shared only after an introduction is accepted.
- Let owners submit listings for moderation and manage private household utility splits with accepted members.

Listing details and photos are owner supplied. Approximate neighborhood locations are shown publicly. Email verification and moderation do not establish property ownership.

## Try it locally

### Docker Compose

Requires Docker Desktop with the Compose plugin.

```powershell
git clone https://github.com/tanay-gaykwad/roomroute.git
cd roomroute
docker compose up --build -d
docker compose exec app python server.py --seed-sample-data
```

Open the app at <http://localhost:8765> and the local email inbox at <http://localhost:8025>. Verification and password-reset messages appear in Mailpit. Sample accounts have no credentials; listings are for browsing only and cannot receive inquiries.

Stop the services with `docker compose down`. Sample records can be removed with `docker compose exec app python server.py --remove-sample-data`.

### Python preview

Requires Python 3.12 or newer.

```powershell
python -m pip install -r requirements.txt
python server.py --seed-sample-data
python server.py
```

Open <http://127.0.0.1:8765>. The local preview uses SQLite and writes verification links to the server terminal when SMTP is not configured. Keep it on your own machine; it is not a public deployment setup.

## Development

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -v
node --check app.js
```

The GitHub Actions workflow also runs PostgreSQL and Redis integration checks, builds the container, and audits Python dependencies. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Project map

| Path | Purpose |
| --- | --- |
| `server.py` | HTTP API, authentication, database access, email outbox, and static routes |
| `app.js`, `*.html`, `*.css` | Browser interface and informational pages |
| `test_server.py` | API, security, account, listing, and service-flow tests |
| `Dockerfile`, `docker-compose.yml` | Local container image and PostgreSQL/Redis/Mailpit stack |
| `render.yaml`, `DEPLOYMENT.md` | Example hosted configuration and deployment notes |
| `SECURITY.md`, `SECURITY_REVIEW.md` | Vulnerability reporting and current security review |

## Current priorities

1. Collect and manually verify owner-authorized pilot listings in the target Nagpur neighborhoods.
2. Add a controlled image upload and review flow instead of external image links.
3. Let owners correct listing details and confirm availability over time.
4. Complete operational checks for hosting, email delivery, backups, monitoring, privacy information, and moderator MFA before real users.

The full checklist and limits are in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md). The project is not cleared for a public launch.

## Contributing and support

Bug reports, focused feature proposals, and small pull requests are welcome. Start with an issue for larger changes so the scope can be agreed before implementation. See [contribution guidelines](CONTRIBUTING.md), [code of conduct](CODE_OF_CONDUCT.md), and [support options](SUPPORT.md).

Please do not put credentials, private user data, or exploitable vulnerability details in public issues. Follow [SECURITY.md](SECURITY.md) for security reports.

## License

RoomRoute's original code is available under the [MIT License](LICENSE). Third-party packages, fonts, and externally hosted photos are governed by their own licenses and terms.
