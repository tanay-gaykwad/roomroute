# RoomRoute security review

**Reviewed:** 2026-10-17
**Scope:** Python HTTP service, PostgreSQL/SQLite schema paths, Redis write limits, account flows, email outbox, listing/report moderation, privacy endpoints, browser UI, and container setup.
**Outcome:** implementation review only. No penetration test or independent audit has been performed.

## Controls added

- Production mode requires a PostgreSQL URL, Redis, SMTP with STARTTLS, HTTPS public URL, and an explicit allowed-host list. The local preview remains loopback-only unless the explicit container flag is set.
- Redis Lua increments/expiry give concurrent app workers a shared atomic fixed-window limit. Database-backed login attempt tracking uses PostgreSQL in service mode.
- Session cookies use a random opaque token whose SHA-256 digest is stored server-side. Production uses `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and the `__Host-` prefix. Mutating authenticated actions require matching Origin and CSRF token.
- Verification and reset tokens are random, hashed at rest, time-limited, and single-use. Reset revokes sessions. Login requires verified email.
- SMTP work is persisted before delivery. Failures retry with backoff; email message content is cleared after successful delivery and sent records are deleted after 14 days.
- New listings start pending; public reads include active listings only. Moderator endpoints require a moderator role. Reports are restricted to active sessions.
- Export and deletion endpoints require an authenticated session; deletion also verifies the current password and removes linked platform records.
- The container runs as a non-root account, local Compose ports bind to loopback, request bodies are bounded, concurrent request threads are capped, and sockets have read timeouts.

## Remaining risks and operating requirements

- The application has not been penetration-tested. The synchronous `ThreadingHTTPServer` is a small service implementation; replace it with a hardened HTTP stack and review reverse-proxy behavior before broad public traffic.
- Email ownership confirmation does not establish that an owner controls or is authorized to rent the advertised property. Add evidence-based owner checks and ongoing listing reconfirmation.
- No user photo upload/storage pipeline is implemented. Existing display images are synthetic stock images; do not publish real listings using those images as evidence.
- SMTP retries are at-least-once: a process can crash after the provider accepts a message and before the database marks it delivered. Some duplicate notices can occur. Configure provider bounce/suppression monitoring.
- Redis outage causes write limiting to fail closed. Monitor Redis availability and alert on HTTP 5xx and outbox age.
- Behind a proxy, set only the real proxy source CIDRs in `ROOMROUTE_TRUST_PROXY_CIDRS`. The service ignores `X-Forwarded-For` from untrusted peers. Set correct TLS termination and host forwarding at the proxy.
- Database backups, restore tests, managed secrets, DNS, SMTP reputation, alerts, retention policy, privacy/terms, grievance handling, and incident procedures require operator setup.
- Synthetic sample records are not actual user accounts or listings. The app blocks sample listing inquiries and seeding a database containing real data.

## Verification performed for this change

Local unit tests cover bounded request bodies, sample-data safety, cookies, Origin/Host validation, and local throttling. CI installs declared dependencies, runs the unit suite and static syntax checks, audits Python dependencies, and builds the Docker image. A live PostgreSQL/Redis/SMTP deployment has not been exercised in this workspace.

