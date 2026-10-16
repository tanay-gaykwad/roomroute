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
- Inquiry form that saves messages about user-created listings to SQLite; only that listing's owner can see them in the inbox. Fictional sample listings reject inquiries.
- Responsive layout for mobile and desktop.

The included 50 owner/listing records and 200 renter profiles (140 students, 60 employees) are fictional sample data and have no sign-in credentials. New owner/renter accounts, listings, and inquiries persist in the local database. Sample owners cannot receive messages. For a real user-created listing, an inquiry appears only in the local owner's inbox; this preview does not send email or SMS. The service binds to loopback only and does not expose data to the internet. Photos load from Unsplash and require an internet connection. This is not a public rental service. See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) and [SECURITY_REVIEW.md](SECURITY_REVIEW.md) before considering a launch.

