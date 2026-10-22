# Production readiness

**Release decision: not cleared for public launch yet.** The named software gaps have implementation paths now, and the repository includes a production-configured backend mode and deployment container. A code change cannot provision hosting, set provider secrets, prove owner identity, write the operator's actual legal commitments, or substitute for a security and restore review.

## Implemented

- PostgreSQL is used when `DATABASE_URL` is configured; production startup refuses SQLite. Schema initialization is additive and recorded in `schema_migrations`.
- Redis uses an atomic Lua fixed-window counter for shared write limits. Production refuses startup without Redis.
- Email verification and password reset use hashed, expiring, single-use tokens. Login is blocked until the account is verified; reset revokes active sessions.
- Inquiries are committed to the database and a durable SMTP outbox. Failures retry with bounded backoff. PostgreSQL row locking avoids duplicate claims by concurrently running outbox workers.
- New listings are private in `pending` state. Moderators approve/reject/pause listings and review user reports. A moderator is created interactively, not through public signup.
- Owners can take their active listing out of public search; relisting returns it to `pending` for a fresh moderator decision.
- Signed-in users can export account data and delete their account, listings, inquiries, reports, sessions, tokens, auth-attempt email traces, and queued email.
- `Dockerfile`, local Postgres/Redis/Mailpit Compose stack, health checks, bounded request threads, and CI container build.
- Sign-in throttling is applied before password verification and shared through Redis by IP and normalized-email hash. Verification and recovery tokens are carried in URL fragments.
- Account creation and sign-in responses no longer disclose whether an email exists or is verified; unknown-account sign-ins use a dummy Argon2 verification.
- Public listing search uses database-side filters and bounded pagination (50 by default, 100 maximum per response). Production config is checked before DB setup; sample-data commands are blocked in production. Worker concurrency is configurable and bounded.

## Required before real users

1. Choose a hosting provider and domain; configure HTTPS, secrets, database/Redis services, SMTP sender verification, and `ROOMROUTE_ALLOWED_HOSTS`. Then confirm `/healthz`, email delivery, session cookies, and fail-closed behavior in that actual environment.
2. Configure encrypted backups, restore drills, monitoring, alerting, log access/retention, incident response, and deployment rollback. No cloud account or operational monitoring is provisioned here.
3. Arrange an independent security review. The code has not had a penetration test. In particular, review the standard-library threaded HTTP server and consider replacing it with a hardened production HTTP stack before a high-traffic public launch.
   Require multi-factor authentication for moderator accounts before staff can access real user records; it is not implemented in this version.
4. Add an owner identity/ownership verification process and a controlled image upload service. Email verification and manual listing review do not prove a poster owns a property. Real listings now show an explicit no-photo placeholder; owners cannot upload or edit photos, and owners cannot edit rent/details after submission.
5. Have the operator prepare accurate terms, privacy notice, consent, retention, grievance contact, and incident procedures and obtain qualified review for the actual Indian service. The account export/deletion endpoints are technical operations, not a complete legal privacy program.
6. Replace the fictional inventory with owner-authorized, checked listings and accurate photos, price, availability, utilities, and safety details. Never represent sample data as real supply or traction.

## Current constraints

- Direct `python server.py` without `DATABASE_URL` is a SQLite local preview. Do not expose it publicly.
- The Docker Compose stack is local development only. Its default passwords and Mailpit are not for a public environment.
- Moderators must triage every new listing and report. There is no automatic owner-document verification or reviewer staffing system.
- Owner listing maintenance is incomplete: owners can pause or request relisting, but cannot edit rent, facilities, availability, or photos after submission.
- Inquiry delivery is email notification plus an in-app owner inbox. SMS, bounce/suppression management, direct reply from email, and customer support are not configured.
- No cloud deployment target, provider credentials, DNS, real inventory, policy text, or independent audit is supplied by the repository.
- There is no measured capacity claim. Run staged load tests against the selected hosting/database plan before launch. The included free-tier preview configuration is deliberately capped at four workers and four database connections; four concurrent Argon2 password checks can still use roughly 256 MiB before Python, database clients, and other memory use. Account export and private inbox/moderation responses still need pagination as histories grow.

