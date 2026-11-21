#!/usr/bin/env bash
# Rebuild the Postgres database from the raw files in data/raw and the files in data/import,
# without downloading anything, then export a candidate snapshot and compare it with the live one.
#
# Usage (from backend/):  scripts/rebuild_database.sh
# Needs: a running Postgres, .venv set up, and data/raw as kept on the main machine.
# It never touches snapshot/threshold.db. It writes snapshot/threshold.rebuilt.db for you to compare.
set -euo pipefail

cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
DB=${DB:-threshold}
export DATABASE_URL=${DATABASE_URL:-postgresql+psycopg://localhost/$DB}

if psql -lqt | cut -d '|' -f 1 | grep -qw "$DB"; then
  echo "Database '$DB' already exists. Drop it first (dropdb $DB) if you want a clean rebuild." >&2
  exit 1
fi

echo "== Creating $DB and its tables"
createdb "$DB"
"$PY" -m alembic upgrade head

echo "== JoSAA, CSAB, seat matrix, institutions and rankings (from data/raw and data/registry)"
"$PY" -m ingest.load

echo "== Records with their source documents (from data/import; each file must be in data/raw)"
"$PY" -m ingest.import_records placements ../data/import/placements_nirf.csv --commit
"$PY" -m ingest.import_records fees ../data/import/fees_official.csv --commit
"$PY" -m ingest.import_records placements ../data/import/placements_branch_reports.csv --commit
"$PY" -m ingest.import_records sectors ../data/import/placement_sectors.csv --commit
"$PY" -m ingest.import_records recruiters ../data/import/placement_recruiters.csv --commit

echo "== Faculty, research and alumni counts (cached files only)"
"$PY" -m ingest.load_academics
WIKIDATA_OFFLINE=1 "$PY" -m ingest.wikidata_alumni

echo "== Candidate snapshot"
"$PY" -m ingest.export_snapshot snapshot/threshold.rebuilt.db

echo "== Comparison with the live snapshot"
"$PY" scripts/compare_snapshots.py snapshot/threshold.db snapshot/threshold.rebuilt.db
