"""Load extracted academic figures and research counts. Safe to re-run.

Usage: python -m ingest.load_academics
Reads data/import/academics_nirf.csv and data/import/research_openalex.json, both generated files.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import AcademicSnapshot, AcademicYearRecord, AuditLog, DataSource, Institution, ResearchOutput, SourceDocument

ROOT = Path(__file__).resolve().parents[2]
ACADEMICS = ROOT / "data" / "import" / "academics_nirf.csv"
OPENALEX = ROOT / "data" / "import" / "research_openalex.json"
SNAPSHOT_FIELDS = (
    "faculty_listed", "faculty_current", "faculty_regular", "faculty_with_phd", "professors", "associate_professors", "assistant_professors",
    "median_experience_months", "students_total", "phd_students",
)
YEAR_FIELDS = (
    "phd_graduated", "sponsored_projects", "sponsored_amount_inr", "consultancy_amount_inr", "patents_published", "patents_granted",
    "library_spend_inr", "equipment_spend_inr",
)


def _ints(row: dict, names: tuple[str, ...]) -> dict:
    return {name: int(row[name]) if row.get(name) else None for name in names}


def _document(db, source: DataSource, row: dict) -> SourceDocument:
    existing = db.scalar(select(SourceDocument).where(SourceDocument.raw_path == row["source_file"]))
    if existing is not None:
        return existing
    data = (ROOT / row["source_file"]).read_bytes()
    document = SourceDocument(
        source_id=source.id, title=row["source_title"], url=row["source_url"], raw_path=row["source_file"],
        sha256=hashlib.sha256(data).hexdigest(), reporting_year=int(row["submission_year"]), fetched_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.flush()
    return document


def main() -> None:
    with SessionLocal() as db:
        slugs = {i.slug: i.id for i in db.scalars(select(Institution))}
        nirf = db.scalar(select(DataSource).where(DataSource.key == "nirf_institute_submissions"))
        openalex = db.scalar(select(DataSource).where(DataSource.key == "openalex"))
        # These tables are generated from documents, so a reload replaces them whole.
        db.execute(delete(AcademicYearRecord))
        db.execute(delete(AcademicSnapshot))
        db.execute(delete(ResearchOutput))
        snapshots = years = 0
        with ACADEMICS.open(newline="") as handle:
            for row in csv.DictReader(handle):
                common = dict(
                    institution_id=slugs[row["institution_slug"]], submission_year=int(row["submission_year"]), category=row["category"],
                    verification_status="official", source_document_id=_document(db, nirf, row).id,
                )
                if row["academic_year"]:
                    db.add(AcademicYearRecord(**common, academic_year=row["academic_year"], **_ints(row, YEAR_FIELDS)))
                    years += 1
                else:
                    db.add(AcademicSnapshot(**common, problems=row["problems"] or None, **_ints(row, SNAPSHOT_FIELDS)))
                    snapshots += 1
        research = 0
        if OPENALEX.exists():
            data = json.loads(OPENALEX.read_text())
            for slug, record in data["matched"].items():
                db.add(ResearchOutput(
                    institution_id=slugs[slug], source_id=openalex.id, external_id=record["openalex_id"], matched_name=record["display_name"],
                    works_count=record["works_count"], cited_by_count=record["cited_by_count"], h_index=record["h_index"],
                    works_by_year=record["works_by_year"], retrieved_at=datetime.fromisoformat(data["retrieved_at"]), verification_status="secondary_unverified",
                ))
                research += 1
        db.add(AuditLog(actor="ingest.load_academics", action="load", entity="academic_snapshots", detail={"snapshots": snapshots, "years": years, "research": research}))
        db.commit()
    print(f"Loaded {snapshots} faculty snapshots, {years} academic years, {research} research records")


if __name__ == "__main__":
    main()
