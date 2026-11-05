"""Import placement or fee records from a CSV. Dry run by default, and all-or-nothing.

Usage:
  python -m ingest.import_records placements ../data/import/placements_nirf.csv
  python -m ingest.import_records fees ../data/import/fees_official.csv --commit

Every row needs a source and a verification status. A changed value for a record that
already exists is reported as a conflict and is never overwritten silently.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AuditLog, DataSource, FeeRecord, Institution, PlacementRecord, PlacementRecruiter, PlacementSector, Programme, SourceDocument

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_STATUS = {"official", "verified", "secondary_unverified", "manual_unverified", "outdated"}
DEFINITIONS = {"nirf_graduation_outcomes", "nirf_graduation_outcomes_overall", "institute_placement_report"}
PLACEMENT_INTS = (
    "total_students", "eligible_students", "graduating_students", "students_placed", "higher_studies_students", "total_offers", "base_students",
    "median_salary_inr", "average_salary_inr", "highest_domestic_salary_inr",
)
FEE_INTS = ("annual_tuition_inr", "annual_hostel_inr", "annual_mess_inr", "annual_other_inr", "one_time_inr", "refundable_deposit_inr", "payable_at_admission_inr")
SALARY_FIELDS = ("median_salary_inr", "average_salary_inr", "highest_domestic_salary_inr")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    created: int = 0
    unchanged: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors and not self.conflicts


def _int(row: dict, name: str, line: int, errors: list[str]) -> int | None:
    raw = (row.get(name) or "").strip().replace(",", "")
    if not raw:
        return None
    if not raw.isdigit():
        errors.append(f"Line {line}: {name} must be a whole number, got {raw!r}")
        return None
    return int(raw)


def _common(row: dict, line: int, errors: list[str]) -> None:
    for name in ("institution_slug", "source_title", "source_url", "verification_status"):
        if not (row.get(name) or "").strip():
            errors.append(f"Line {line}: {name} is required")
    status = (row.get("verification_status") or "").strip()
    if status == "test_fixture":
        errors.append(f"Line {line}: test fixtures cannot be imported into the application database")
    elif status and status not in ALLOWED_STATUS:
        errors.append(f"Line {line}: unknown verification_status {status!r}")
    url = (row.get("source_url") or "").strip()
    if url and not url.startswith("https://") and not url.startswith("http://"):
        errors.append(f"Line {line}: source_url must be a web address")


def validate_placement(row: dict, line: int, errors: list[str]) -> dict:
    _common(row, line, errors)
    values = {name: _int(row, name, line, errors) for name in PLACEMENT_INTS}
    scope = (row.get("scope") or "").strip()
    programme_id = _int(row, "programme_id", line, errors)
    if scope not in ("institution", "programme"):
        errors.append(f"Line {line}: scope must be institution or programme")
    if scope == "institution" and programme_id is not None:
        errors.append(f"Line {line}: institute-wide data cannot name a programme")
    if scope == "programme" and programme_id is None and not (row.get("programme_name") or "").strip():
        errors.append(f"Line {line}: programme scope needs a programme_id or programme_name")
    definition = (row.get("reporting_definition") or "").strip()
    if definition not in DEFINITIONS:
        errors.append(f"Line {line}: reporting_definition must be one of {sorted(DEFINITIONS)}")
    if not (row.get("cohort_label") or "").strip():
        errors.append(f"Line {line}: cohort_label is required, e.g. All 4-year UG programmes")
    year = _int(row, "graduation_year", line, errors)
    if year is None or not 2000 <= year <= 2100:
        errors.append(f"Line {line}: graduation_year is missing or implausible")
    for name in SALARY_FIELDS:
        if values[name] is not None and not 100_000 <= values[name] <= 50_000_000:
            errors.append(f"Line {line}: {name} {values[name]} is outside the plausible range. Amounts must be full rupees a year")
    placed = values["students_placed"]
    if values["base_students"] is not None and not (row.get("base_label") or "").strip():
        errors.append(f"Line {line}: base_students needs a base_label saying who that group is")
    for base in ("eligible_students", "graduating_students", "total_students", "base_students"):
        if placed is not None and values[base] is not None and placed > values[base]:
            errors.append(f"Line {line}: students_placed {placed} exceeds {base} {values[base]}")
    if values["median_salary_inr"] is None and placed is None:
        errors.append(f"Line {line}: a record needs at least a median salary or a placed count")
    return {
        **values, "scope": scope, "programme_id": programme_id, "cohort_label": (row.get("cohort_label") or "").strip(),
        "reporting_definition": definition, "graduation_year": year,
        "base_label": (row.get("base_label") or "").strip() or None, "salary_basis": (row.get("salary_basis") or "").strip() or None,
    }


def validate_fee(row: dict, line: int, errors: list[str]) -> dict:
    _common(row, line, errors)
    values = {name: _int(row, name, line, errors) for name in FEE_INTS}
    year = (row.get("academic_year") or "").strip()
    if len(year) != 7 or year[4] != "-" or not (year[:4] + year[5:]).isdigit():
        errors.append(f"Line {line}: academic_year must look like 2026-27")
    if all(v is None for v in values.values()):
        errors.append(f"Line {line}: a fee record needs at least one amount")
    group = (row.get("seat_type_group") or "").strip()
    if not group:
        errors.append(f"Line {line}: seat_type_group is required, because fees vary by category and income")
    return {**values, "academic_year": year, "seat_type_group": group}


def validate_sector(row: dict, line: int, errors: list[str]) -> dict:
    _common(row, line, errors)
    students = _int(row, "students", line, errors)
    if students is None:
        errors.append(f"Line {line}: students is required")
    for name in ("academic_year", "cohort_label", "sector"):
        if not (row.get(name) or "").strip():
            errors.append(f"Line {line}: {name} is required")
    return {"academic_year": (row.get("academic_year") or "").strip(), "cohort_label": (row.get("cohort_label") or "").strip(), "sector": (row.get("sector") or "").strip(), "students": students}


def validate_recruiter(row: dict, line: int, errors: list[str]) -> dict:
    _common(row, line, errors)
    for name in ("academic_year", "company_name"):
        if not (row.get(name) or "").strip():
            errors.append(f"Line {line}: {name} is required")
    return {"academic_year": (row.get("academic_year") or "").strip(), "company_name": (row.get("company_name") or "").strip()}


def resolve_programme(db: Session, inst: Institution, row: dict, values: dict, line: int, errors: list[str]) -> None:
    """Match a programme by its JoSAA name and duration, so rows survive a database rebuild."""
    name = (row.get("programme_name") or "").strip()
    if not name or values.get("programme_id") is not None:
        return
    duration = int((row.get("programme_years") or "4").strip())
    degree = (row.get("programme_degree") or "Bachelor of Technology").strip()
    matches = db.scalars(select(Programme).where(Programme.institution_id == inst.id, Programme.name == name, Programme.duration_years == duration, Programme.degree == degree)).all()
    if len(matches) != 1:
        errors.append(f"Line {line}: found {len(matches)} programmes at {inst.slug} named {name!r} ({duration} years, {degree})")
        return
    values["programme_id"] = matches[0].id


def _source_document(db: Session, row: dict, line: int, errors: list[str], cache: dict) -> SourceDocument | None:
    key = (row.get("source_key") or "").strip()
    source = db.scalar(select(DataSource).where(DataSource.key == key))
    if source is None:
        errors.append(f"Line {line}: unknown source_key {key!r}. Add it to data/registry/sources.yaml and reload")
        return None
    url = (row.get("source_url") or "").strip()
    file_name = (row.get("source_file") or "").strip()
    if file_name:
        path = ROOT / file_name
        if not path.exists():
            errors.append(f"Line {line}: source_file not found: {file_name}")
            return None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        digest = None
        errors.append(f"Line {line}: source_file is required so the exact document is kept")
        return None
    if digest in cache:
        return cache[digest]
    document = db.scalar(select(SourceDocument).where(SourceDocument.source_id == source.id, SourceDocument.sha256 == digest))
    if document is None:
        year = (row.get("reporting_year") or "").strip()
        document = SourceDocument(
            source_id=source.id, title=row["source_title"].strip(), url=url, raw_path=file_name, sha256=digest,
            reporting_year=int(year) if year.isdigit() else None,
        )
        db.add(document)
        db.flush()
    else:
        document.title = row["source_title"].strip()
    cache[digest] = document
    return document


def _meta(row: dict) -> dict:
    page = (row.get("source_page") or "").strip()
    return {
        "verification_status": (row.get("verification_status") or "").strip(),
        "source_page": int(page) if page.isdigit() else None, "notes": (row.get("notes") or "").strip() or None,
    }


VALIDATORS = {"placements": validate_placement, "fees": validate_fee, "sectors": validate_sector, "recruiters": validate_recruiter}
MODELS = {
    "placements": (PlacementRecord, ("programme_id", "cohort_label", "graduation_year")),
    "fees": (FeeRecord, ("academic_year", "seat_type_group")),
    "sectors": (PlacementSector, ("academic_year", "cohort_label", "sector")),
    "recruiters": (PlacementRecruiter, ("academic_year", "company_name")),
}


def run(db: Session, kind: str, path: Path, commit: bool) -> Report:
    report = Report()
    institutions = {i.slug: i for i in db.scalars(select(Institution))}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        report.errors.append("The file has no rows")
        return report
    documents: dict = {}
    seen: set = set()
    changes = []
    for line, row in enumerate(rows, start=2):
        errors: list[str] = []
        values = VALIDATORS[kind](row, line, errors)
        inst = institutions.get((row.get("institution_slug") or "").strip())
        if inst is None:
            errors.append(f"Line {line}: unknown institution_slug {row.get('institution_slug')!r}")
        if kind == "placements" and inst is not None:
            resolve_programme(db, inst, row, values, line, errors)
        if kind == "placements" and values.get("programme_id") is not None and inst is not None:
            programme = db.get(Programme, values["programme_id"])
            if programme is None or programme.institution_id != inst.id:
                errors.append(f"Line {line}: programme {values['programme_id']} does not belong to {inst.slug}")
        document = _source_document(db, row, line, errors, documents) if not errors else None
        if errors or document is None:
            report.errors.extend(errors)
            continue
        values.update(_meta(row))
        model, keys = MODELS[kind]
        identity = (inst.id, document.id, *(values[k] for k in keys))
        conditions = [model.institution_id == inst.id, model.source_document_id == document.id]
        conditions += [getattr(model, k).is_not_distinct_from(values[k]) for k in keys]
        existing = db.scalar(select(model).where(*conditions))
        if identity in seen:
            report.errors.append(f"Line {line}: duplicate of an earlier row in this file")
            continue
        seen.add(identity)
        if existing is not None:
            different = {k: (getattr(existing, k), v) for k, v in values.items() if getattr(existing, k) != v}
            if different:
                report.conflicts.append(f"Line {line}: {inst.slug} differs from the stored record: {different}")
            else:
                report.unchanged += 1
            continue
        changes.append(model(institution_id=inst.id, source_document_id=document.id, **values))
    report.created = len(changes)
    if not report.ok:
        db.rollback()
        return report
    # A dry run also writes and rolls back, so it finds what database constraints would reject.
    db.add_all(changes)
    try:
        db.flush()
    except (DataError, IntegrityError) as error:
        db.rollback()
        report.errors.append(f"The database rejected this file: {str(error.orig).strip()}")
        return report
    if commit:
        db.add(AuditLog(
            actor="ingest.import_records", action="import", entity=kind,
            detail={"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "created": report.created, "unchanged": report.unchanged},
        ))
        db.commit()
    else:
        db.rollback()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=sorted(VALIDATORS))
    parser.add_argument("file", type=Path)
    parser.add_argument("--commit", action="store_true", help="write to the database. Without this, only checks")
    args = parser.parse_args()
    with SessionLocal() as db:
        report = run(db, args.kind, args.file, args.commit)
    for message in report.errors + report.conflicts:
        print(message)
    state = "written" if args.commit and report.ok else "not written"
    print(f"{args.kind}: {report.created} new, {report.unchanged} unchanged, {len(report.errors)} errors, {len(report.conflicts)} conflicts ({state})")
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
