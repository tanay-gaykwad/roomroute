# Production readiness

**Release decision: NO-GO for public production or real user data.** This repository remains a local preview. The server intentionally refuses `APP_ENV=production` and refuses non-loopback bind addresses. Do not bypass those checks.

## Changes in this review

- Sample seeding now refuses to run if any non-sample owner, renter, or listing records exist. It no longer relabels user records as samples.
- Sample listings cannot accept inquiries; the interface identifies them as fictional and shows no contact form.
- Public owner data is limited to owners with active listings.
- JSON request bodies must be bounded objects with a valid content type and length. Writes for registration, inquiries, and listings have a local per-IP limit.
- Session-cookie security no longer trusts the client-supplied `X-Forwarded-Proto` header. Production cookie naming/security and HTTPS-only Origin checks are prepared, but production startup remains disabled.
- Added a database health endpoint and tightened listing input validation.
- The earlier production guard is retained because these code changes do not provide a production database, verified identity, message delivery, moderation, or launch operations.

## Required before accepting real users

1. **Replace SQLite for service use.** Use PostgreSQL, managed credentials, schema migrations, connection pooling, automated encrypted backups, and a tested restore. Add distributed rate limiting and a shared session store before running multiple instances.
2. **Complete identity flows.** Add verified email with expiring single-use tokens, password reset, account recovery, session/device management, secure account deletion, and independent authentication review. Unverified accounts must not publish listings or send inquiries.
3. **Protect inquiry delivery.** Choose and configure an email or in-app notification provider, delivery retries, bounce handling, anti-spam controls, abuse reporting, blocking, and retention. The current app only saves local inbox records.
4. **Support trustworthy listings.** Build owner verification and review queue, owner-controlled listing edit/archive, availability reconfirmation, moderation, controlled image upload/storage, report handling, and audit trails. Do not imply verification or reviews that have not been earned.
5. **Complete privacy and legal launch work.** Add user-reviewed privacy notice, terms, consent, data export/deletion, contact and grievance routes, retention and incident-response policies, and review of applicable Indian privacy, consumer, rental-advertising, and intermediary requirements. The repository cannot supply accurate legal commitments without the operator's real policies and counsel review.
6. **Deploy and operate securely.** Select a host and domain; configure HTTPS, trusted-host/proxy settings, managed secrets, WAF/edge limits, monitoring, alerting, dependency scanning, CI/CD, vulnerability reporting, backups, rollback, and incident response. Run a third-party security review before production.
7. **Replace example inventory.** Obtain consent and verify owners, addresses, photos, availability, rent, deposits, utility rules, and occupancy terms. Remove sample data only after confirming the backup and replacement data.

## Current operational limits

- Loopback-only Python `ThreadingHTTPServer`; not a production-grade ASGI/WSGI server.
- SQLite data and rate limits are local to one process and one computer.
- No email verification, password recovery, email/SMS delivery, image upload, moderation workflow, account deletion/export, or real owner verification.
- The included 50 listings and 200 renter profiles are fictional. They are not evidence of live supply, reviews, verified owners, or market demand.

Use [SECURITY_REVIEW.md](SECURITY_REVIEW.md) as the review record. The service should remain local until each release gate has an owner, implementation, and verification evidence.

