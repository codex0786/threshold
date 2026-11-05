# Deployment

**A public, read-only prototype is deployed on Vercel. It isn't production-ready:** see the checklist below.

## Public deployment
There are two Vercel projects in team `ab-c4`, both deployed from this machine with the CLI, so pushing to GitHub doesn't change the site.

| Project | Folder | Notes |
|---|---|---|
| `threshold` | `frontend/` | https://threshold-india.vercel.app. Next.js. `API_BASE_URL` points at the API, and `/api/v1/*` is rewritten to it. |
| `threshold-api` | `backend/` | https://threshold-india-api.vercel.app. FastAPI through `index.py`, reading a bundled SQLite snapshot. |

Vercel's generated addresses sit behind Vercel login, so each project uses the `threshold-india*` address above. After deploying the API, run `vercel alias set <deployment-url> threshold-india-api.vercel.app --scope ab-c4` if the address hasn't moved to the new deployment. Building the frontend needs a reachable API, because the home and methodology pages are generated at build time and refreshed hourly.

`index.py` turns on read-only mode, so nothing a student enters is stored. It also sets a rate limit and turns off the API docs. The limit is counted per server instance, so it slows abuse but isn't a hard cap. It returned 429s on direct calls to the API, while a burst of 160 calls through the site wasn't limited.

The snapshot (`backend/snapshot/threshold.db`) is git-ignored, so the bulk dataset isn't in the public repository. To publish new data:

```bash
cd backend
.venv/bin/python -m ingest.export_snapshot
vercel deploy --prod --yes --scope ab-c4
```

Before publishing a data change, compare API responses from Postgres and the snapshot. They differ only in alphabetical tie-order and timestamp timezones.

## Run locally
Needs Python 3.12, Node, and PostgreSQL.

```bash
createdb threshold && createdb threshold_test
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m ingest.josaa_fetch --years 2021-2025 --current
.venv/bin/python -m ingest.load
.venv/bin/python -m ingest.nirf_fetch
.venv/bin/python -m ingest.fetch_fee_documents
.venv/bin/python -m ingest.import_records placements ../data/import/placements_nirf.csv --commit
.venv/bin/python -m ingest.import_records fees ../data/import/fees_official.csv --commit
.venv/bin/python -m ingest.import_records placements ../data/import/placements_branch_reports.csv --commit
.venv/bin/python -m ingest.import_records sectors ../data/import/placement_sectors.csv --commit
.venv/bin/python -m ingest.import_records recruiters ../data/import/placement_recruiters.csv --commit
.venv/bin/python -m ingest.wikidata_alumni
.venv/bin/uvicorn app.main:app --port 8400
```

```bash
cd frontend
npm install
npm run dev
```

The app opens at `http://localhost:3400`. Raw downloads aren't in git, so a fresh setup fetches them again. Please keep that infrequent, as it uses a public government service.

## Planned production shape
- FastAPI on a container host, once accounts need writes.
- Managed PostgreSQL, with `DATABASE_URL`.
- Object storage for raw source documents.

These involve paid services and external accounts, so each needs approval.

## Pre-production checklist
- [ ] Authentication and authorisation (needed before anything is written)
- [ ] Rate limiting shared across instances (today's limit is per instance)
- [ ] Retention policy for `recommendation_runs`, plus a review against India's data protection rules (not stored on the public deployment)
- [ ] Written position on JoSAA data reuse
- [ ] Official NIRF data replaces the secondary source
- [ ] Institute locations reviewed
- [ ] Clause 11 exceptions resolved
- [ ] Rules reviewed for the new counselling year
- [ ] Backups and migration rollback plan
- [ ] Security review
