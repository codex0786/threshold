"""Compare two SQLite snapshots table by table, by content rather than by id.

Usage: python scripts/compare_snapshots.py LIVE.db CANDIDATE.db

Ids differ between builds, so each row is compared by its values with id and timestamp columns
left out, and foreign keys are compared by what they point to where that is cheap (institution
slug, programme raw name). Exit code 0 only when every table matches.
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter

SKIP_COLUMNS = {"id", "created_at", "updated_at", "fetched_at", "retrieved_at", "loaded_at", "last_checked_at"}
SKIP_TABLES = {"alembic_version", "recommendation_runs", "audit_logs"}


def tables(db: sqlite3.Connection) -> list[str]:
    return [r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]


def lookups(db: sqlite3.Connection) -> dict[str, dict[int, str]]:
    """Ids that rows point to, replaced by stable names."""
    out: dict[str, dict[int, str]] = {}
    names = set(tables(db))
    if "institutions" in names:
        out["institution_id"] = dict(db.execute("select id, slug from institutions"))
    if "programmes" in names:
        out["programme_id"] = {i: f"{s}|{n}" for i, s, n in db.execute("select p.id, i.slug, p.raw_name from programmes p join institutions i on i.id = p.institution_id")}
        out["successor_id"] = out["programme_id"]
    if "source_documents" in names:
        out["source_document_id"] = {i: f"{sha}" for i, sha in db.execute("select id, sha256 from source_documents")}
    if "data_sources" in names:
        out["source_id"] = dict(db.execute("select id, key from data_sources"))
    return out


def rows(db: sqlite3.Connection, table: str) -> tuple[list[str], Counter]:
    cols = [r[1] for r in db.execute(f"pragma table_info('{table}')")]
    kept = [c for c in cols if c not in SKIP_COLUMNS]
    maps = lookups(db)
    counter: Counter = Counter()
    for row in db.execute(f"select {', '.join(kept)} from '{table}'"):
        values = []
        for col, value in zip(kept, row):
            if col in maps and value is not None:
                value = maps[col].get(value, f"?{value}")
            if isinstance(value, float):
                value = round(value, 6)
            values.append(value)
        counter[tuple(values)] += 1
    return kept, counter


def main(live_path: str, candidate_path: str) -> int:
    live, candidate = sqlite3.connect(live_path), sqlite3.connect(candidate_path)
    all_tables = sorted((set(tables(live)) | set(tables(candidate))) - SKIP_TABLES)
    failures = 0
    for table in all_tables:
        if table not in tables(live) or table not in tables(candidate):
            print(f"{table:32} only in {'live' if table in tables(live) else 'candidate'}")
            failures += 1
            continue
        live_cols, a = rows(live, table)
        cand_cols, b = rows(candidate, table)
        if live_cols != cand_cols:
            print(f"{table:32} columns differ: {sorted(set(live_cols) ^ set(cand_cols))}")
            failures += 1
            continue
        missing, extra = a - b, b - a
        status = "same" if not missing and not extra else f"DIFFERENT: {sum(missing.values())} only in live, {sum(extra.values())} only in candidate"
        print(f"{table:32} live {sum(a.values()):>7}  candidate {sum(b.values()):>7}  {status}")
        if missing or extra:
            failures += 1
            for label, diff in (("live only", missing), ("candidate only", extra)):
                for values, _ in list(diff.items())[:3]:
                    print(f"    {label}: {dict(zip(live_cols, values))}")
    print("\nAll tables match." if not failures else f"\n{failures} table(s) differ. Don't replace the live snapshot until each difference is understood.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
