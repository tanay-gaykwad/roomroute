# RoomRoute security review

**Reviewed:** 2026-10-18
**Scope:** Python HTTP service, PostgreSQL/SQLite schema paths, Redis write limits, account flows, email outbox, listing/report moderation, privacy endpoints, browser UI, and container setup.
**Outcome:** implementation review only. No penetration test or independent audit has been performed.

## Controls added

- Production mode requires a PostgreSQL URL, Redis, SMTP with STARTTLS, HTTPS public URL, and an explicit allowed-host list. The local preview remains loopback-only unless the explicit container flag is set.
- Redis Lua increments/expiry give concurrent app workers a shared atomic fixed-window limit. Database-backed login attempt tracking uses PostgreSQL in service mode.
- Session cookies use a random opaque token whose SHA-256 digest is stored server-side. Production uses `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and the `__Host-` prefix. Mutating authenticated actions require matching Origin and CSRF token.
- Verification and reset tokens are random, hashed at rest, time-limited, and single-use. Reset revokes sessions. Login requires verified email.
- SMTP work is persisted before delivery. Failures retry with backoff; email message content is cleared after successful delivery and sent records are deleted after 14 days.
- New listings start pending; public reads include active listings only. Moderator endpoints require a moderator role. Reports are restricted to active sessions.
- Owners can withdraw active listings from public search; reopening a paused listing sends it back for moderator review.
- Real listings do not display the stock sample photo. The UI states when the owner has not supplied photos.
- Export and deletion endpoints require an authenticated session; deletion also verifies the current password and removes linked platform records.
- The container runs as a non-root account, local Compose ports bind to loopback, request bodies are bounded, concurrent request threads are capped, and sockets have read timeouts.
- Login is rate limited before Argon2 work by both source IP and a one-way hash of the normalized email. Production uses Redis shared across workers and fails closed if Redis is unavailable.
- Verification and reset links carry their one-time token in the URL fragment, which browsers do not send to the HTTP server or include in referrer headers. Old query-style links remain accepted for already-sent mail.
- Login and registration responses avoid telling a caller whether an email is already registered or verified. Unknown-account login checks use a precomputed dummy Argon2 hash for comparable password work.
- Public inventory reads are filtered and paginated in PostgreSQL/SQLite, with a maximum of 100 listings per response. Count queries and owner data are scoped to the selected page.
- Production config is validated before database initialization. Production blocks sample data operations and cannot fall back to SQLite. The threaded server defaults to 16 workers and production configuration bounds it to 4–32.

## Remaining risks and operating requirements

- The application has not been penetration-tested. The synchronous `ThreadingHTTPServer` is a small service implementation; replace it with a hardened HTTP stack and review reverse-proxy behavior before broad public traffic.
- No representative load test has been run, so there is no defensible maximum record count, request rate, or user count yet. Pagination bounds public listing responses; actual capacity still depends on the chosen app memory/CPU, PostgreSQL plan, pool size, Redis, and image/email providers. Argon2 is configured for 65,536 KiB per password operation; the showcase blueprint limits the app to four workers and four database connections, allowing roughly 256 MiB of simultaneous hash working memory at peak before Python and other service memory. This remains a preview setting, not a capacity guarantee. Choose worker count and app memory together and test login bursts before launch.
- Account export and several private inbox/moderation endpoints still return each account's full matching history in one response. Add cursor pagination and retention/archival policy before those datasets become large.
- Email ownership confirmation does not establish that an owner controls or is authorized to rent the advertised property. Add evidence-based owner checks and ongoing listing reconfirmation.
- Moderator accounts do not yet require multi-factor authentication. Require MFA for every moderator before granting staff access to real user data.
- No user photo upload/storage pipeline is implemented. Sample photos are synthetic; real listings show a placeholder until an approved upload flow exists. Owners also cannot edit listing details after submission, which creates availability and accuracy risk.
- SMTP retries are at-least-once: a process can crash after the provider accepts a message and before the database marks it delivered. Some duplicate notices can occur. Configure provider bounce/suppression monitoring.
- Redis outage causes write limiting to fail closed. Monitor Redis availability and alert on HTTP 5xx and outbox age.
- Behind a proxy, set only the real proxy source CIDRs in `ROOMROUTE_TRUST_PROXY_CIDRS`. The service ignores `X-Forwarded-For` from untrusted peers. Set correct TLS termination and host forwarding at the proxy.
- Database backups, restore tests, managed secrets, DNS, SMTP reputation, alerts, retention policy, privacy/terms, grievance handling, and incident procedures require operator setup.
- Synthetic sample records are not actual user accounts or listings. The app blocks sample listing inquiries and seeding a database containing real data.

## Verification performed for this change

Local unit tests cover bounded request bodies, sample-data safety, cookies, Origin/Host validation, owner listing availability transitions, and local throttling. Listing serialization tests ensure real records do not inherit sample photos and expose creation timestamps for sorting. CI installs declared dependencies, runs the unit suite and static syntax checks, audits Python dependencies, and builds the Docker image. A live PostgreSQL/Redis/SMTP deployment has not been exercised in this workspace.

