"""Copy the published tables from Postgres into a read-only SQLite file for the public deployment.

Run logs are left out: they hold profiles entered while using the tool.
    python -m ingest.export_snapshot [output path]
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, select, text

from app.db import engine as source
from app.models import Base

SKIP = {"recommendation_runs", "audit_logs"}
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "snapshot" / "threshold.db"
BATCH = 5000


def main(output: Path = DEFAULT_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    target = create_engine(f"sqlite:///{output}")
    Base.metadata.create_all(target)
    with source.connect() as read, target.begin() as write:
        for table in Base.metadata.sorted_tables:
            if table.name in SKIP:
                continue
            rows = [dict(r._mapping) for r in read.execute(select(table))]
            for start in range(0, len(rows), BATCH):
                write.execute(table.insert(), rows[start:start + BATCH])
            print(f"{table.name}: {len(rows)}")
    with target.begin() as write:
        write.execute(text("PRAGMA journal_mode=DELETE"))
    with target.connect() as conn:
        conn.exec_driver_sql("VACUUM")
    print(f"Wrote {output} ({output.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT)
