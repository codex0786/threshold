"""Load registries and parsed JoSAA tables into Postgres. Safe to re-run.

Usage: python -m ingest.load
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    AuditLog, CsabCutoff, CutoffRecord, DataSource, Institution, InstitutionAlias, InstitutionRanking, Programme,
    QuotaEligibleState, SeatMatrixRecord, SourceDocument,
)
from app.services.branches import branch_family, campus_of, required_paper
from app.services.eligibility import exam_for, rank_list_name
from ingest import nirf_official
from ingest.csab_fetch import QUOTAS as CSAB_QUOTAS, SKIPPED_QUOTAS as CSAB_SKIPPED
from ingest.josaa_parse import RawRow, clean, parse_file, parse_programme, parse_rank
from ingest.seat_matrix import parse as parse_seat_matrix

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
RAW = ROOT / "data" / "raw" / "josaa"
RAW_CSAB = ROOT / "data" / "raw" / "csab"

SEAT_TYPES = {
    "OPEN": "OPEN", "EWS": "EWS", "OBC-NCL": "OBC-NCL", "SC": "SC", "ST": "ST",
    "OPEN (PwD)": "OPEN-PwD", "EWS (PwD)": "EWS-PwD", "OBC-NCL (PwD)": "OBC-NCL-PwD",
    "SC (PwD)": "SC-PwD", "ST (PwD)": "ST-PwD",
}
GENDER_POOLS = {"Gender-Neutral": "neutral", "Female-only (including Supernumerary)": "female"}

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
    websites = {}
    placements = ROOT / "data" / "import" / "placements_nirf.csv"
    if placements.exists():
        with placements.open(newline="") as handle:
            for row in csv.DictReader(handle):
                websites[row["institution_slug"]] = "https://" + urlsplit(row["source_url"]).netloc
    for entry in yaml.safe_load((REGISTRY / "institutions.yaml").read_text()):
        inst = db.scalar(select(Institution).where(Institution.slug == entry["slug"])) or Institution(slug=entry["slug"])
        inst.official_name = clean(entry["names"][0])
        inst.short_name = entry["short"]
        inst.institute_type = entry["type"]
        inst.city = entry.get("city")
        inst.state = entry["state"]
        # Otherwise use the site that published this institute's own accepted NIRF document.
        inst.website = entry.get("website") or websites.get(entry["slug"])
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
    """NIRF ranks from secondary copies. Each rank the official list confirms is stored as official instead."""
    official = nirf_official.official_list()
    total = 0
    for filename, source_key in (("nirf_2025_engineering_secondary.yaml", "nirf_2025_careers360"), ("nirf_2025_engineering_top100_secondary.yaml", "nirf_2025_top100_copies")):
        rows = yaml.safe_load((REGISTRY / filename).read_text())
        for row in rows:
            stmt = insert(InstitutionRanking).values(
                institution_id=by_slug[row["slug"]].id, framework="NIRF", category="Engineering", year=2025,
                rank=row["rank"], score=row["score"],
                **({"verification_status": "official", "source_id": sources[nirf_official.SOURCE_KEY].id}
                   if nirf_official.confirm(official, row["slug"], by_slug[row["slug"]].official_name, row["rank"])
                   else {"verification_status": "secondary_unverified", "source_id": sources[source_key].id}),
            ).on_conflict_do_nothing()
            db.execute(stmt)
        total += len(rows)
    return total


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


def _source_document(db: Session, source: DataSource, meta: dict, raw_folder: str, title: str, row_count: int) -> SourceDocument:
    doc = db.scalar(select(SourceDocument).where(SourceDocument.source_id == source.id, SourceDocument.sha256 == meta["sha256"]))
    if doc is None:
        doc = SourceDocument(
            source_id=source.id, title=title, url=meta["url"], raw_path=f"data/raw/{raw_folder}/{meta['file']}", sha256=meta["sha256"],
            reporting_year=meta["year"], fetched_at=datetime.fromisoformat(meta["fetched_at"]), row_count=row_count,
        )
        db.add(doc)
        db.flush()
    return doc


def refresh_programme_labels(db: Session) -> list[str]:
    """Apply the current naming rules to stored programmes, and report each change."""
    changes = []
    for programme in db.scalars(select(Programme)):
        family = branch_family(programme.name)
        if family != programme.branch_family:
            changes.append(f"{programme.name}: {programme.branch_family} to {family}")
            programme.branch_family = family
        campus = campus_of(programme.name)
        programme.campus_city, programme.campus_country = campus if campus else (None, None)
    return sorted(set(changes))


def load_lineage(db: Session, by_slug: dict[str, Institution]) -> int:
    pairs = yaml.safe_load((REGISTRY / "programme_lineage.yaml").read_text())
    db.execute(update(Programme).values(successor_id=None))
    for pair in pairs:
        inst_id = by_slug[pair["institution"]].id
        earlier = db.scalar(select(Programme).where(Programme.institution_id == inst_id, Programme.raw_name == pair["earlier"]))
        later = db.scalar(select(Programme).where(Programme.institution_id == inst_id, Programme.raw_name == pair["later"]))
        if earlier is None or later is None:
            raise ValueError(f"programme_lineage.yaml names a programme that doesn't exist: {pair}")
        earlier.successor_id = later.id
    return len(pairs)


def load_seat_matrix(db: Session, source: DataSource, by_alias: dict[str, Institution], programmes: dict) -> dict[int, dict[str, set[str]]]:
    """Store seats, and return each institute's home states exactly as the seat matrix prints them."""
    home_states: dict[int, dict[str, set[str]]] = {}
    for path in sorted(RAW.glob("seatmatrix_*.html")):
        meta = json.loads(path.with_suffix(".json").read_text())
        rows = parse_seat_matrix(path.read_text(encoding="utf-8"))
        doc = _source_document(db, source, meta, "josaa", f"JoSAA {meta['year']} seat matrix", len(rows))
        values = {}
        for row in rows:
            inst = by_alias.get(row.institute)
            programme = programmes.get((inst.id, row.programme)) if inst else None
            if programme is None:
                raise UnmappedInstitution(f"{path.name}: the seat matrix names an unknown programme: {row.institute}: {row.programme}")
            quota = row.quota
            # NIT Goa's first list is Goa alone, which JoSAA's rank tables call the Goa quota.
            if quota == "HS" and row.states == ("Goa",) and inst.slug == "nit-goa":
                quota = "GO"
            if quota in ("HS", "GO", "JK", "LA"):
                home_states.setdefault(inst.id, {}).setdefault(quota, set()).update(row.states)
            for seat_type, seats in row.seats.items():
                values[(programme.id, meta["year"], quota, seat_type, row.gender_pool)] = {
                    "programme_id": programme.id, "year": meta["year"], "quota": quota, "seat_type": seat_type,
                    "gender_pool": row.gender_pool, "seats": seats, "source_document_id": doc.id,
                }
        batch = list(values.values())
        for start in range(0, len(batch), 2000):
            db.execute(insert(SeatMatrixRecord).values(batch[start:start + 2000]).on_conflict_do_nothing(constraint="uq_seat_identity"))
        print(f"{path.name}: {len(batch):,} seat cells")
    return home_states


def load_quota_states(db: Session, home_states: dict[int, dict[str, set[str]]], by_slug: dict[str, Institution]) -> int:
    """Replace the home-state list with the official one, and mark each institute whose state it confirms."""
    db.query(QuotaEligibleState).delete()
    confirmed = 0
    for inst in by_slug.values():
        quotas = home_states.get(inst.id, {})
        for quota, states in quotas.items():
            for state in states:
                db.add(QuotaEligibleState(institution_id=inst.id, quota=quota, state=state))
        if inst.state in set().union(*quotas.values(), set()):
            inst.location_verification = "state_official"
            confirmed += 1
    return confirmed


def load_csab(db: Session, source: DataSource, by_alias: dict[str, Institution], programmes: dict) -> int:
    """Only programmes already known from JoSAA are stored. Anything else is reported, not guessed at."""
    total = 0
    skipped: set[tuple[str, str]] = set()
    for path in sorted(RAW_CSAB.glob("csab_*.html")):
        meta = json.loads(path.with_suffix(".json").read_text())
        rows = parse_file(path)
        doc = _source_document(db, source, meta, "csab", f"CSAB special round {meta['round']}, {meta['year']}: opening and closing ranks", len(rows))
        values = {}
        for row in rows:
            if row.quota in CSAB_SKIPPED:
                continue
            quota = CSAB_QUOTAS[row.quota]
            inst = by_alias.get(row.institute)
            programme = programmes.get((inst.id, row.programme)) if inst else None
            opening, opening_prep = parse_rank(row.opening)
            closing, closing_prep = parse_rank(row.closing)
            if programme is None:
                skipped.add((row.institute, row.programme))
                continue
            if opening_prep or closing_prep:
                continue
            values[(programme.id, quota, row.seat_type, row.gender)] = {
                "programme_id": programme.id, "year": meta["year"], "round": meta["round"], "quota": quota,
                "seat_type": SEAT_TYPES[row.seat_type], "gender_pool": GENDER_POOLS[row.gender],
                "opening_rank": opening, "closing_rank": closing, "source_document_id": doc.id,
            }
        batch = list(values.values())
        for start in range(0, len(batch), 2000):
            db.execute(insert(CsabCutoff).values(batch[start:start + 2000]).on_conflict_do_nothing(constraint="uq_csab_identity"))
        total += len(batch)
    if skipped:
        print(f"CSAB programmes with no JoSAA match, left out ({len(skipped)}):", sorted(skipped))
    return total


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
        db.flush()
        relabelled = refresh_programme_labels(db)
        lineage = load_lineage(db, by_slug)
        home_states = load_seat_matrix(db, sources["josaa_seat_matrix"], by_alias, programmes)
        confirmed = load_quota_states(db, home_states, by_slug)
        csab = load_csab(db, sources["csab_special"], by_alias, programmes)
        db.add(AuditLog(actor="ingest.load", action="load", entity="cutoff_records", detail={"rows": total, "rankings": ranking_count, "csab": csab}))
        db.commit()
        print(f"Loaded {total:,} cutoff rows, {len(programmes):,} programmes, {ranking_count} rankings, {csab:,} CSAB rows, {lineage} renames")
        print(f"State confirmed by the seat matrix: {confirmed} institutes")
        print("Relabelled:", relabelled)


if __name__ == "__main__":
    main()
