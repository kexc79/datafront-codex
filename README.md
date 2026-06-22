# DataFront

DataFront is an engineering MVP for tracking incoming report files, their processing status, and Oracle-backed business dictionaries.

## Quick Start

1. Copy `.env.example` to `.env` and fill passwords, Oracle credentials, and optional AG Grid license keys.
2. Keep deployment credentials in `.env.deploy.local`; do not commit that file.
3. Put Oracle Instant Client files into `oracle/instantclient` on the server. Oracle 11g requires thick mode.
4. Start the stack:

```bash
docker compose up --build
```

The UI is served on `http://localhost:5137`, and the API is available at `http://localhost:8000/api/v1`.

## First Login

The first administrator is created automatically from:

- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_NAME`

Change the password after the first login.

## Main Screens

- Engineer: expected report list, grouped report view, file upload, row/pack statistics, comments, feedback status.
- Admin matrix: enables real customer/project pairs after Oracle customer/project sync.
- Admin plan: creates expected reports by customer/project, country, data type, distributor, period, and deadline.
- Oracle: syncs configured dictionaries from Oracle. Missing SQL queries are shown as warnings.
- Users: creates users with `admin`, `engineer`, or `customer` roles.

## MVP Boundaries

- Oracle 11g is read-only in this version.
- DataFront metadata is stored in Postgres.
- Original uploaded files are stored in a Docker volume.
- The first administrator is created from `.env` on API startup.
- Customer access scopes are implemented in the API; the UI can be expanded with a dedicated scope editor when customer accounts are introduced.

## Checks

```bash
python -m pytest
docker compose config --quiet
```
