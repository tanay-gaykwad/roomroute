# RoomRoute security review

**Reviewed:** 2026-10-17  
**Scope:** the checked-in Python HTTP server, browser client, SQLite schema, sample-data lifecycle, and public repository contents.  
**Outcome:** not approved for public service. This is a code review, not a penetration test or legal review.

## Findings addressed in this change

- **Sample-data deletion could affect real renter accounts (high):** seeding previously marked every existing row as sample. It now refuses to seed any database with non-sample owners, users, or listings; it leaves existing rows unchanged.
- **Fictional listings accepted inquiries (medium):** those messages could never reach a real owner. The API now rejects them and the UI labels the owner/listing as fictional.
- **Unlisted account names were exposed by the public owner API (medium):** public owner records are now limited to owners with active listings.
- **Cookie transport relied on a client-controlled forwarded header (high if deployed behind a proxy):** cookie security now derives only from server configuration; production uses a `__Host-` cookie and HTTPS-only Origin checks. Public startup remains blocked.
- **Unbounded/non-object JSON and weak write throttling (medium):** request bodies are size/content-type/object checked; registration, inquiry, and listing writes have local per-IP limits.
- **Listing values were incompletely validated (medium):** property type, area, furnishing, date, text bounds, and boolean fields are checked before insert.

## Open launch blockers

- No verified-email or password-recovery flow. `is_verified` exists in the schema but is not an enforceable user journey. Do not permit real public registration until verification is implemented and required for protected actions.
- SQLite and local per-process throttles are not appropriate for a horizontally scaled or resilient public service. There are no migrations, managed backups, or restore evidence.
- Inquiries are database records only. No owner notifications, message delivery guarantees, spam controls, block/report tools, or moderation operations exist.
- Owners cannot upload controlled property photos, manage listing lifecycle, prove ownership, or reconfirm availability. Example imagery/data cannot substantiate the advertised properties.
- Privacy notice/terms, data export/deletion, retention, grievance process, and incident response are not implemented. India-specific legal review needs the operator's real service policies and qualified review.
- No production host/domain, secrets manager, monitoring, alerts, CI security scan, tested backups, or independent penetration test is configured.

## Release controls

- `APP_ENV=production` and non-loopback bind addresses are rejected by design.
- Never publish real renter/owner records in this repository. The SQLite database is ignored by Git.
- Keep sample labels visible. Seed data must not be represented as actual inventory, verified ownership, ratings, or activity.
- Re-review this document and the launch checklist after completing each blocker; do not flip the production guard as a substitute for the missing controls.

