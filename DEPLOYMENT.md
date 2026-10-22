# Deployment guide

## Local service stack

1. Install Docker Desktop.
2. From this directory, run `docker compose up --build`.
3. Visit `http://localhost:8765`; inspect verification/reset mail at `http://localhost:8025`.
4. Create a moderation account with `docker compose exec app python server.py --create-moderator`.
5. Optional synthetic inventory: `docker compose exec app python server.py --seed-sample-data`.

The app waits for healthy PostgreSQL and Redis services. Data persists in named Docker volumes. To reset local demo data, use the specific sample removal command; deleting volumes destroys all local accounts and app data.

## Render Blueprint

The repository includes `render.yaml` for a Singapore-region Render web service, managed PostgreSQL, and Redis-compatible Key Value. Its free plans are only a showcase configuration: the web service has limited memory and spins down after inactivity, free Postgres expires after 30 days, and free services are unsuitable for production data. Do not store real user data in this setup. See [Render's free instance limitations](https://render.com/docs/free). The Blueprint stores no email credentials or public hostname in Git. It caps the app at four request workers and four database connections because each concurrent Argon2 password operation uses about 64 MiB; these limits are a starting point for a preview, not a measured capacity guarantee.

1. In Render, create a Blueprint from the `tanay-gaykwad/roomroute` GitHub repository. The resources are set to Free; verify the plan in the dashboard before applying it.
2. After Render creates the web service, open its Environment settings and set `ROOMROUTE_PUBLIC_URL` to its HTTPS `onrender.com` URL and `ROOMROUTE_ALLOWED_HOSTS` to the matching hostname without `https://`.
3. Set `SMTP_HOST` and `SMTP_FROM` to a verified sender from your transactional email provider. If the provider requires login, add `SMTP_USERNAME` and `SMTP_PASSWORD` there as secret environment variables. `SMTP_STARTTLS=1` and port `587` are configured by the Blueprint.
4. Save the environment and wait for the service health check at `/healthz` to pass. Production startup deliberately refuses traffic until the URL, host allowlist, and SMTP sender are configured.
5. Configure database backups, restore checks, alerting, and an operator-owned recovery process before accepting real users. Create the first moderator using the documented secure, interactive setup process; never put moderator credentials in Blueprint variables.

The web service reads Render's `PORT` variable when `ROOMROUTE_PORT` is not explicitly set. Database and Key Value connection strings are injected by service references and are not stored in the repository.

## Public container deployment

Use the image built from this directory on a provider that supports Python containers. Provision managed PostgreSQL and Redis; configure TLS at the provider's load balancer or reverse proxy; configure SMTP with a verified sending domain; and store every password/URL as a managed secret. Required settings:

| Setting | Example | Purpose |
| --- | --- | --- |
| `APP_ENV` | `production` | Enables production cookie and startup requirements |
| `DATABASE_URL` | `postgresql://...` | Shared PostgreSQL database, preferably with provider-required TLS |
| `ROOMROUTE_DB_POOL_SIZE` | `20` | Per-instance maximum database connections; size total across replicas under the database limit |
| `REDIS_URL` | `rediss://...` | Shared Redis for atomic write limits |
| `ROOMROUTE_PUBLIC_URL` | `https://rooms.example` | Email links and canonical service URL |
| `ROOMROUTE_ALLOWED_HOSTS` | `rooms.example` | Host header allowlist (hostnames, without scheme) |
| `ROOMROUTE_TRUST_PROXY_CIDRS` | `10.0.0.0/8` | Optional actual proxy networks for client IP extraction |
| `SMTP_HOST`, `SMTP_PORT` | `smtp.example`, `587` | Outbox transport |
| `SMTP_STARTTLS` | `1` | Requires encrypted SMTP transport in production |
| `SMTP_FROM` | `RoomRoute <no-reply@example>` | Verified sender identity |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | provider values | Required when the provider authenticates |

Run one instance first, confirm health and all auth/email/moderation flows, and only then scale replicas. Outbox rows are claimed with PostgreSQL locks. Configure database backups and restore, Redis monitoring, SMTP bounces/suppression, application alerts, log retention, rollout/rollback, and an operator-owned incident process before launch. Create the first moderator with an interactive one-off command; do not put moderator passwords in deployment files.

The app image does not provide HTTPS, DNS, a cloud account, an automated production deployment, user-upload storage, legal documents, or owner identity checks. Do not put real inventory online until those launch operations are complete.

