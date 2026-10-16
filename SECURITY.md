# Security policy

## Supported deployment

The repository includes a local preview and a production-configured mode. Production mode requires PostgreSQL, Redis, SMTP/STARTTLS, HTTPS URL and an explicit host allowlist. A configuration gate does not certify a deployment; see [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md). Do not store real personal information in the SQLite local preview or local Compose defaults.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository (Security tab → Report a vulnerability) when available. Do not include exploitable details in a public issue. If private reporting is unavailable, contact the repository owner privately before publishing details.

## Response

The repository owner should acknowledge a report, assess impact, prepare a fix, and coordinate disclosure. No response-time SLA is promised until an operator and incident-response process are established.

