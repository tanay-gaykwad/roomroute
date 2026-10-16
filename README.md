# RoomRoute prototype

A local RoomRoute product preview for finding student rooms and flats in Nagpur, Maharashtra.

## Run the working local preview

Run the local server from this folder:

```powershell
python server.py
```

Then visit `http://127.0.0.1:8765`.

To load the synthetic starter records into an empty local database:

```powershell
python server.py --seed-sample-data
```

To remove only records marked as sample data after real records have been added:

```powershell
python server.py --remove-sample-data
```

The local database is `roomroute.sqlite3`. Back it up before removal. Normal server startup never seeds records automatically. `APP_ENV=production` and non-loopback bind addresses are deliberately rejected while production authentication, PostgreSQL, and deployment protections are unfinished.

## Current preview features

- 50 fictional owners, each with one fictional room or flat listing.
- 200 fictional renter profiles: 140 students and 60 employees.
- Search by Nagpur neighborhood, property type, budget, furnishing, parking, and electricity costs.
- Searchable listing details and a shortlist saved in browser storage.
- Local owner/renter registration and sign-in with owner-only workspace access.
- Owner form that creates a listing in SQLite and immediately makes it searchable.
- Inquiry form that saves messages to SQLite; only the listing owner can see them in the inbox.
- Responsive layout for mobile and desktop.

The included 50 owner/listing records and 200 renter profiles (140 students, 60 employees) are fictional sample data and have no sign-in credentials. New owner/renter accounts, listings, and inquiries persist in the local database. The service binds to loopback only and does not contact owners or expose data to the internet. Photos load from Unsplash and require an internet connection. The local account flow is not a public identity or email verification system. This is not yet a public rental service; see [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for launch blockers.

