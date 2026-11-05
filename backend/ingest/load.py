"""Load registries and parsed JoSAA tables into Postgres. Safe to re-run.

Usage: python -m ingest.load
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    AuditLog, CutoffRecord, DataSource, Institution, InstitutionAlias, InstitutionRanking, Programme,
    QuotaEligibleState, SourceDocument,
)
from app.services.branches import branch_family, required_paper
from app.services.eligibility import exam_for, rank_list_name
from ingest.josaa_parse import RawRow, clean, parse_file, parse_programme, parse_rank

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
RAW = ROOT / "data" / "raw" / "josaa"

SEAT_TYPES = {
    "OPEN": "OPEN", "EWS": "EWS", "OBC-NCL": "OBC-NCL", "SC": "SC", "ST": "ST",
    "OPEN (PwD)": "OPEN-PwD", "EWS (PwD)": "EWS-PwD", "OBC-NCL (PwD)": "OBC-NCL-PwD",
    "SC (PwD)": "SC-PwD", "ST (PwD)": "ST-PwD",
}
GENDER_POOLS = {"Gender-Neutral": "neutral", "Female-only (including Supernumerary)": "female"}

# Business Rules 2026, clauses 11 and 12. Everything else with HS seats uses its own state.
NORTH_EAST_MALDA = ["Arunachal Pradesh", "Assam", "Nagaland", "Manipur", "Meghalaya", "Mizoram", "Sikkim", "Tripura"]
QUOTA_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "nit-goa": {"GO": ["Goa"], "HS": ["Daman and Diu", "Dadra and Nagar Haveli", "Lakshadweep"]},
    "nit-srinagar": {"JK": ["Jammu and Kashmir"], "LA": ["Ladakh"]},
    "nit-puducherry": {"HS": ["Puducherry", "Andaman and Nicobar Islands"]},
    "nit-delhi": {"HS": ["Delhi", "Chandigarh"]},
    "gkciet-malda": {"HS": NORTH_EAST_MALDA},
}


class UnmappedInstitution(ValueError):
    pass


def load_sources(db: Session) -> dict[str, DataSource]:
    now = datetime.now(timezone.utc)
    out = {}
    for entry in yaml.safe_load((REGISTRY / "sources.yaml").read_text()):
        source = db.scalar(select(DataSource).where(DataSource.key == entry["key"])) or DataSource(key=entry["key"])
        for field, value in entry.items():
            setattr(source, field, value)
        source.last_checked_at = now
        db.add(source)
        out[entry["key"]] = source
    db.flush()
    return out


def load_institutions(db: Session) -> tuple[dict[str, Institution], dict[str, Institution]]:
    by_alias: dict[str, Institution] = {}
    by_slug: dict[str, Institution] = {}
    for entry in yaml.safe_load((REGISTRY / "institutions.yaml").read_text()):
        inst = db.scalar(select(Institution).where(Institution.slug == entry["slug"])) or Institution(slug=entry["slug"])
        inst.official_name = clean(entry["names"][0])
        inst.short_name = entry["short"]
        inst.institute_type = entry["type"]
        inst.city = entry.get("city")
        inst.state = entry["state"]
        inst.website = entry.get("website")
        inst.is_pilot = bool(entry.get("website"))
        inst.location_verification = "manual_unverified"
        db.add(inst)
        db.flush()
        existing = {a.alias for a in inst.aliases}
        for name in entry["names"]:
            alias = clean(name)
            if alias not in existing:
                inst.aliases.append(InstitutionAlias(alias=alias))
            by_alias[alias] = inst
        by_slug[inst.slug] = inst
    db.flush()
    return by_alias, by_slug


def load_rankings(db: Session, by_slug: dict[str, Institution], sources: dict[str, DataSource]) -> int:
    rows = yaml.safe_load((REGISTRY / "nirf_2025_engineering_secondary.yaml").read_text())
    for row in rows:
        stmt = insert(InstitutionRanking).values(
            institution_id=by_slug[row["slug"]].id, framework="NIRF", category="Engineering", year=2025,
            rank=row["rank"], score=row["score"], verification_status="secondary_unverified",
            source_id=sources["nirf_2025_careers360"].id,
        ).on_conflict_do_nothing()
        db.execute(stmt)
    return len(rows)


def row_values(row: RawRow, programme: Programme, inst: Institution, year: int, round_no: int, is_final: bool, doc_id: int) -> dict:
    opening, opening_prep = parse_rank(row.opening)
    closing, closing_prep = parse_rank(row.closing)
    seat_type = SEAT_TYPES[row.seat_type]
    return {
        "programme_id": programme.id, "authority": "JOSAA", "year": year, "round": round_no,
        "is_final_round": is_final, "quota": row.quota, "seat_type": seat_type,
        "gender_pool": GENDER_POOLS[row.gender],
        "rank_list": rank_list_name(exam_for(inst.institute_type), seat_type),
        "opening_rank": opening, "closing_rank": closing,
        "is_preparatory": opening_prep or closing_prep,
        "raw_opening": row.opening, "raw_closing": row.closing, "source_document_id": doc_id,
    }


def load_table(db: Session, path: Path, source: DataSource, by_alias: dict[str, Institution], programmes: dict) -> int:
    meta = json.loads(path.with_suffix(".json").read_text())
    rows = parse_file(path)
    unknown = sorted({r.institute for r in rows} - by_alias.keys())
    if unknown:
        raise UnmappedInstitution(f"{path.name}: add these names to institutions.yaml: {unknown}")
    doc = db.scalar(select(SourceDocument).where(SourceDocument.source_id == source.id, SourceDocument.sha256 == meta["sha256"]))
    if doc is None:
        doc = SourceDocument(
            source_id=source.id, title=f"JoSAA {meta['year']} Round {meta['round']} opening and closing ranks",
            url=meta["url"], raw_path=f"data/raw/josaa/{path.name}", sha256=meta["sha256"],
            reporting_year=meta["year"], fetched_at=datetime.fromisoformat(meta["fetched_at"]), row_count=len(rows),
        )
        db.add(doc)
        db.flush()
    values = []
    for row in rows:
        inst = by_alias[row.institute]
        key = (inst.id, row.programme)
        programme = programmes.get(key)
        if programme is None:
            name, years, degree = parse_programme(row.programme)
            programme = Programme(
                institution_id=inst.id, raw_name=row.programme, name=name, branch_family=branch_family(name),
                degree=degree, duration_years=years, required_paper=required_paper(inst.institute_type, degree, name),
            )
            db.add(programme)
            db.flush()
            programmes[key] = programme
        values.append(row_values(row, programme, inst, meta["year"], meta["round"], meta["is_final_round"], doc.id))
    # The source sometimes repeats a row. The first occurrence is kept and the rest are counted.
    unique = {(v["programme_id"], v["quota"], v["seat_type"], v["gender_pool"]): v for v in reversed(values)}
    for start in range(0, len(unique), 2000):
        batch = list(unique.values())[start:start + 2000]
        db.execute(insert(CutoffRecord).values(batch).on_conflict_do_nothing(constraint="uq_cutoff_identity"))
    print(f"{path.name}: {len(rows):,} rows, {len(rows) - len(unique)} duplicates skipped")
    return len(unique)


def load_quota_states(db: Session, by_slug: dict[str, Institution]) -> list[str]:
    """Record home states from the institutes that actually publish those quotas."""
    pairs = db.execute(
        select(Programme.institution_id, CutoffRecord.quota).join(CutoffRecord.programme)
        .where(CutoffRecord.quota.in_(["HS", "GO", "JK", "LA"])).distinct()
    ).all()
    by_id = {i.id: i for i in by_slug.values()}
    db.query(QuotaEligibleState).delete()
    defaulted = set()
    for inst_id, quota in pairs:
        inst = by_id[inst_id]
        override = QUOTA_OVERRIDES.get(inst.slug, {})
        if quota in override:
            states = override[quota]
        else:
            states = [inst.state]
            defaulted.add(inst.short_name)
        for state in states:
            db.add(QuotaEligibleState(institution_id=inst_id, quota=quota, state=state))
    return sorted(defaulted)


def main() -> None:
    with SessionLocal() as db:
        sources = load_sources(db)
        if "--registry-only" in sys.argv:
            db.commit()
            print(f"Refreshed {len(sources)} sources")
            return
        by_alias, by_slug = load_institutions(db)
        ranking_count = load_rankings(db, by_slug, sources)
        programmes = {(p.institution_id, p.raw_name): p for p in db.scalars(select(Programme))}
        total = 0
        for path in sorted(RAW.glob("orcr_*.html")):
            total += load_table(db, path, sources["josaa_orcr"], by_alias, programmes)
            db.flush()
        defaulted = load_quota_states(db, by_slug)
        db.add(AuditLog(actor="ingest.load", action="load", entity="cutoff_records", detail={"rows": total, "rankings": ranking_count}))
        db.commit()
        print(f"Loaded {total:,} cutoff rows, {len(programmes):,} programmes, {ranking_count} rankings")
        print("Institutes using their own state as home state:", defaulted)


if __name__ == "__main__":
    main()
