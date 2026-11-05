# Deployment

**Nothing has been deployed, and this slice isn't ready for it.** Auth, rate limiting and the open data-rights question must be resolved first. Deployment needs explicit approval.

## Run locally
Needs Python 3.12, Node, and PostgreSQL.

```bash
createdb threshold && createdb threshold_test
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
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
- Frontend on Vercel, with `API_BASE_URL` pointing at the backend.
- FastAPI on a container host.
- Managed PostgreSQL, with `DATABASE_URL`.
- Object storage for raw source documents.

These involve paid services and external accounts, so each needs approval.

## Pre-production checklist
- [ ] Authentication and authorisation
- [ ] Rate limiting
- [ ] Retention policy for `recommendation_runs`, plus a review against India's data protection rules
- [ ] Written position on JoSAA data reuse
- [ ] Official NIRF data replaces the secondary source
- [ ] Institute locations reviewed
- [ ] Clause 11 exceptions resolved
- [ ] Rules reviewed for the new counselling year
- [ ] Backups and migration rollback plan
- [ ] Security review
