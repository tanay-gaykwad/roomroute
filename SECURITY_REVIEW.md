# RoomRoute security review

**Reviewed:** 2026-10-28
**Scope:** Python HTTP service, PostgreSQL/SQLite schema paths, Redis write limits, account flows, email outbox, listing/report moderation, privacy endpoints, browser UI, and container setup.
**Outcome:** source and automated test review only. This is not a penetration test or independent security audit, and it cannot guarantee that the service will not be compromised.

## Controls added

- Production mode requires a PostgreSQL URL, Redis, SMTP with STARTTLS, HTTPS public URL, and an explicit allowed-host list. The local preview remains loopback-only unless the explicit container flag is set.
- Redis Lua increments/expiry give concurrent app workers a shared atomic fixed-window limit. Database-backed login attempt tracking uses PostgreSQL in service mode.
- Session cookies use a random opaque token whose SHA-256 digest is stored server-side. Production uses `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and the `__Host-` prefix. Mutating authenticated actions require matching Origin and CSRF token.
- Verification and reset tokens are random, hashed at rest, time-limited, and single-use. Reset revokes sessions. Login requires verified email.
- SMTP work is persisted before delivery. Failures retry with backoff; email message content is cleared after successful delivery and sent records are deleted after 14 days.
- New listings start pending; public reads include active listings only. Moderator endpoints require a moderator role. Reports are restricted to active sessions.
- Owners can withdraw active listings from public search; reopening a paused listing sends it back for moderator review.
- Real listings do not display stock sample photos. Owners can provide up to eight HTTPS image links; the server restricts links to HTTPS but does not fetch or inspect the image content. A listing with no gallery shows a no-photo message.
- Export and deletion endpoints require an authenticated session; deletion also verifies the current password and removes linked platform records.
- The container runs as a non-root account, local Compose ports bind to loopback, request bodies are bounded, concurrent request threads are capped, and sockets have read timeouts.
- Login is rate limited before Argon2 work by both source IP and a one-way hash of the normalized email. Production uses Redis shared across workers and fails closed if Redis is unavailable.
- Verification and reset links carry their one-time token in the URL fragment, which browsers do not send to the HTTP server or include in referrer headers. Old query-style links remain accepted for already-sent mail.
- Login and registration responses avoid telling a caller whether an email is already registered or verified. Unknown-account login checks use a precomputed dummy Argon2 hash for comparable password work.
- Public inventory reads are filtered and paginated in PostgreSQL/SQLite, with a maximum of 100 listings per response. Count queries and owner data are scoped to the selected page.
- Production config is validated before database initialization. Production blocks sample data operations and cannot fall back to SQLite. The threaded server defaults to 16 workers and production configuration bounds it to 4â€“32.
- Static content is served from a route allowlist; tests confirm repository files, dotfiles, and the local SQLite database return 404. CORS is not enabled because the web UI and API are same-origin.
- Content Security Policy now blocks inline scripts/styles, plugins, framing, and non-same-origin API calls; the response also disables unused browser permissions and cross-domain policy files. HSTS is sent only in production.
- The browser connection-error view inserts server-provided error text as text nodes rather than interpreting it as HTML.
- Renter-owner conversations and messages are stored in the database with participant-scoped reads/writes, CSRF/origin protection, message length limits, and rate limits. Message bodies render as escaped text; the admin role cannot read private conversation endpoints.
- Listing metadata includes owner-stated accessibility, student eligibility, pet rules, utilities, parking, and amenities. Public location remains approximate. Inquiry move-in dates and owner-managed open/dismissed states are stored with the inquiry.
- Roommate profiles are opt-in and available to verified renters. Email addresses are withheld until an introduction is accepted; accepted users see each other’s account email.
- Household utility ledgers are limited to owners and accepted household members. Invitations require renter acceptance, and the per-person bill split excludes the owner. The ledger records amounts; it does not handle payments.

## Remaining risks and operating requirements

- The application has not been penetration-tested. The synchronous `ThreadingHTTPServer` is a small service implementation; replace it with a hardened HTTP stack and review reverse-proxy behavior before broad public traffic.
- No representative load test has been run, so there is no defensible maximum record count, request rate, or user count yet. Pagination bounds public listing responses; actual capacity still depends on the chosen app memory/CPU, PostgreSQL plan, pool size, Redis, and image/email providers. Argon2 is configured for 65,536 KiB per password operation; the showcase blueprint limits the app to four workers and four database connections, allowing roughly 256 MiB of simultaneous hash working memory at peak before Python and other service memory. This remains a preview setting, not a capacity guarantee. Choose worker count and app memory together and test login bursts before launch.
- Account export and several private inbox/moderation endpoints still return each account's full matching history in one response. Add cursor pagination and retention/archival policy before those datasets become large.
- Email ownership confirmation does not establish that an owner controls or is authorized to rent the advertised property. Add evidence-based owner checks and ongoing listing reconfirmation.
- Moderator accounts do not yet require multi-factor authentication. Require MFA for every moderator before granting staff access to real user data.
- No binary photo upload, image type/content validation, re-encoding, or managed object storage is implemented. External HTTPS images are requested by the renter’s browser and may disclose a page visit and network metadata to the image host. Owners also cannot edit listing details after submission, which creates availability and accuracy risk.
- SMTP retries are at-least-once: a process can crash after the provider accepts a message and before the database marks it delivered. Some duplicate notices can occur. Configure provider bounce/suppression monitoring.
- Redis outage causes write limiting to fail closed. Monitor Redis availability and alert on HTTP 5xx and outbox age.
- Behind a proxy, set only the real proxy source CIDRs in `ROOMROUTE_TRUST_PROXY_CIDRS`. The service ignores `X-Forwarded-For` from untrusted peers. Set correct TLS termination and host forwarding at the proxy.
- Database backups, restore tests, managed secrets, DNS, SMTP reputation, alerts, retention policy, privacy/terms, grievance handling, and incident procedures require operator setup.
- Synthetic sample records are not actual user accounts or listings. The app blocks sample listing inquiries and seeding a database containing real data.

## Verification performed for this change

Local tests passed on 2026-10-28: 21 tests passed and one PostgreSQL/Redis integration test was skipped because `TEST_POSTGRES_URL` was not configured. Coverage includes the existing account, moderation, privacy, throttling, static-file, and conversation checks, plus listing metadata/photo links and filters, inquiry move-in dates/status, opt-in roommate introductions and contact disclosure, household invitations, bill visibility, and bill calculations. Python and browser JavaScript syntax checks passed. A live PostgreSQL/Redis/SMTP deployment, deployment environment variables, external database backups, and a representative load test have not been validated in this workspace.

