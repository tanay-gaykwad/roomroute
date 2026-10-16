# Production readiness status

**Status: local product preview; not safe to deploy as a public rental service.** The current server refuses production mode and non-loopback addresses by design.

## What is already separated

- Every seeded owner, renter profile, and listing carries an `is_sample` marker.
- The starter dataset is loaded explicitly with `python server.py --seed-sample-data`; normal startup does not recreate it.
- `python server.py --remove-sample-data` deletes only marked sample records and their dependent inquiries.
- The SQLite file is local-only and excluded from source control.

## Required before a public launch

1. **Accounts and authorization:** a first local account flow now uses Argon2id password hashes, HttpOnly/SameSite cookies, CSRF and Origin checks, login throttling, and owner/renter role checks. Before launch, add verified-email flows, password recovery, stronger distributed rate limits, session revocation controls, and independent security review.
2. **Production database:** PostgreSQL, schema migrations, encrypted backups, restore practice, retention policy, and a tested sample-data removal migration.
3. **Privacy and contact safety:** consent and privacy notice, data export/deletion, message retention rules, private contact details, and a data-breach response plan.
4. **Abuse controls:** production edge rate limits, spam protection, reporting/blocking, listing review queue, dispute handling, and an accountable moderation process. Current login throttling is local to the SQLite file and does not protect a horizontally scaled service.
5. **Listing integrity:** real owner onboarding, availability reconfirmation, truthful verification criteria, photo upload/storage controls, and no fabricated ratings or activity.
6. **Deployment and operations:** HTTPS, managed secrets, security headers, dependency updates, error monitoring, audit logs, health checks, CI, restore testing, and documented incident response.
7. **Nagpur launch review:** check local requirements for rental advertising, privacy, reviews, consumer disclosures, and any intermediary obligations before accepting real users.

The seeded records are suitable for exercising UI and data workflows. They are not evidence of real Nagpur rental supply, verified owners, user reviews, or customer demand.

