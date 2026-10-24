# RoomRoute

RoomRoute is an independent software project for finding and listing rental rooms and flats in Nagpur. It is being built as a portfolio product, with a focused neighborhood pilot, renter search and shortlisting, owner listing submission, and service-side safeguards. It is not a college DBMS project.

The repository includes an explicitly labelled synthetic preview dataset for trying the interface. Those records are not real rentals, contacts, reviews, or users.

**Launch status: local preview, not a live public service in this repository snapshot.** Newly submitted real listings do not yet have photo upload; the UI deliberately shows “Owner photos not provided” instead of a stock image. Do not use fictional records or sample photos to imply real availability.

## Run the preview

For the quickest local run, Python 3.12+ is required:

```powershell
python -m pip install -r requirements.txt
python server.py --seed-sample-data
python server.py
```

Open <http://127.0.0.1:8765>. This direct command uses a local SQLite file for isolated development. If SMTP is not configured, verification/recovery links are written to that local server's terminal output. Do not expose this mode to the internet.

## Run the service stack locally

Docker Compose starts the app with PostgreSQL, Redis, and a local Mailpit inbox. The app binds to loopback only.

```powershell
docker compose up --build
```

Open the app at <http://localhost:8765> and the local email inbox at <http://localhost:8025>. Account verification and password-reset emails appear in Mailpit. Load the fictional inventory with:

```powershell
docker compose exec app python server.py --seed-sample-data
```

The sample owners, listings, and renter profiles are synthetic and have no credentials. Their listings are explicitly labelled and cannot receive inquiries. Remove only sample rows with `docker compose exec app python server.py --remove-sample-data`.

## Service features

- PostgreSQL-backed data with a bounded connection pool when `DATABASE_URL` is set; production refuses to start without PostgreSQL.
- Shared Redis fixed-window throttles for registration, listing creation, inquiries, and password-reset email requests.
- Argon2 password storage, verified-email requirement, expiring single-use verification and password-reset tokens, secure production cookies, CSRF checks, and session revocation on password reset.
- Inquiry records saved to PostgreSQL and queued in a durable SMTP outbox. The outbox retries failures and uses PostgreSQL row locks so replicas do not send the same pending message concurrently.
- New owner listings remain private until a moderator approves them. Authenticated users can report listings; moderators can review or dismiss reports.
- The initial neighborhood pilot is Lokmanya Nagar, Digdoh Hills, Wanadongri, Hingna Road, and Hingna MIDC. Other Nagpur areas remain selectable for the existing preview.
- Each listing states whether rent and deposit apply per person/bed or to the whole place. New owner submissions require an authorization attestation, stored with its submission time; this is not proof of ownership and manual checks are still required.
- Owner submissions must state whether maintenance is included, separately charged, or not charged. Legacy/sample records remain “not specified” rather than being assigned a guessed cost. Browse budget and sort controls compare rent; separately billed maintenance and electricity are displayed separately and should be confirmed with the owner.
- Owners can mark an active listing unavailable; bringing it back requires moderator review. Owners still cannot edit listing details after submission.
- Signed-in users can download an account export and delete their account and associated listings, inquiries, reports, sessions, and queued email.
- Docker image runs as a non-root user; Compose health checks gate app startup on PostgreSQL and Redis readiness.

Create the first moderator interactively after starting the service:

```powershell
docker compose exec app python server.py --create-moderator
```

## Production deployment

Deploy the image to a container platform and provide managed PostgreSQL, Redis, and a verified SMTP sender through its secret manager. Set `APP_ENV=production`, `DATABASE_URL`, `REDIS_URL`, `ROOMROUTE_PUBLIC_URL` (`https://...`), `ROOMROUTE_ALLOWED_HOSTS`, `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_STARTTLS=1`, and `SMTP_FROM`. Set `SMTP_USERNAME` and `SMTP_PASSWORD` where the provider requires authentication. Startup refuses production mode if required configuration is missing. HTTPS termination and DNS must be configured at the hosting provider or trusted reverse proxy. If using a proxy, set `ROOMROUTE_TRUST_PROXY_CIDRS` to its actual source networks; forwarded client IPs are ignored otherwise.

Never use the Compose default passwords or Mailpit for a public deployment. Use managed encrypted database/Redis services, backups with restore drills, alerting, log retention, and a reviewed domain email setup. Do not seed fictional data in a real environment. The app does not provision a cloud host, DNS, provider accounts, SMTP credentials, legal terms, or privacy notices for you.

See [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY.md](SECURITY.md), [SECURITY_REVIEW.md](SECURITY_REVIEW.md), and [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) before a public launch.

## Supplementary database report

An optional database-focused report and its regeneration script are in [`docs/reports/`](docs/reports/). This supplementary document follows a previously requested academic format; it does not define RoomRoute’s identity or imply that every documented service capability is deployed. Rebuild it with `python docs/reports/build_report.py` after installing the optional report-generation dependency listed in `docs/reports/requirements.txt`.

