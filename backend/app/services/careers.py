"""Where graduates go: branch outcomes, sectors, recruiters and a labelled alumni sample."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AlumniObservation, PlacementRecord, PlacementRecruiter, PlacementSector, Programme

MIN_ALUMNI_SAMPLE = 30
ALUMNI_CAVEAT = (
    "Counts of people on Wikidata who list this institute as alma mater. This is a small public sample of notable people, skewed to researchers, "
    "and it includes postgraduate and PhD students. It is not the alumni network and says little about typical B.Tech graduates."
)


def branch_outcomes(db: Session, institution_id: int) -> list[dict]:
    """The latest published result per branch. Only comparable within one report."""
    rows = db.execute(
        select(PlacementRecord, Programme.name).join(Programme, Programme.id == PlacementRecord.programme_id)
        .options(joinedload(PlacementRecord.source_document))
        .where(PlacementRecord.institution_id == institution_id, PlacementRecord.scope == "programme")
        .order_by(PlacementRecord.graduation_year.desc())
    ).all()
    if not rows:
        return []
    latest = rows[0][0].graduation_year
    current = [(r, name) for r, name in rows if r.graduation_year == latest]
    current.sort(key=lambda item: (-(item[0].median_salary_inr or 0), -(item[0].students_placed or 0), item[1]))
    return [
        {
            "programme_id": r.programme_id, "programme": name, "graduation_year": r.graduation_year, "students_placed": r.students_placed,
            "base_students": r.base_students, "base_label": r.base_label, "total_students": r.total_students, "median_salary_inr": r.median_salary_inr,
            "average_salary_inr": r.average_salary_inr, "salary_basis": r.salary_basis, "source_title": r.source_document.title,
            "source_url": r.source_document.url, "source_page": r.source_page, "verification_status": r.verification_status, "notes": r.notes,
        } for r, name in current
    ]


def outcome_mix(db: Session, institution_id: int) -> list[dict]:
    """What each NIRF graduating class did next. Anyone not counted is unknown, not unemployed."""
    rows = db.scalars(
        select(PlacementRecord).options(joinedload(PlacementRecord.source_document))
        .where(PlacementRecord.institution_id == institution_id, PlacementRecord.reporting_definition.like("nirf_%"))
        .order_by(PlacementRecord.graduation_year)
    ).all()
    return [
        {
            "graduation_year": r.graduation_year, "graduating_students": r.graduating_students, "students_placed": r.students_placed,
            "higher_studies_students": r.higher_studies_students, "source_title": r.source_document.title, "source_url": r.source_document.url,
        } for r in rows if r.graduating_students
    ]


def sectors(db: Session, institution_id: int) -> dict | None:
    rows = db.scalars(select(PlacementSector).options(joinedload(PlacementSector.source_document)).where(PlacementSector.institution_id == institution_id)).all()
    if not rows:
        return None
    year = max(r.academic_year for r in rows)
    current = sorted((r for r in rows if r.academic_year == year), key=lambda r: -r.students)
    total = sum(r.students for r in current)
    return {
        "academic_year": year, "cohort_label": current[0].cohort_label, "total": total,
        "items": [{"sector": r.sector, "students": r.students, "percent": round(100 * r.students / total, 1)} for r in current],
        "source_title": current[0].source_document.title, "source_url": current[0].source_document.url, "source_page": current[0].source_page,
    }


def recruiters(db: Session, institution_id: int) -> dict | None:
    rows = db.scalars(select(PlacementRecruiter).options(joinedload(PlacementRecruiter.source_document)).where(PlacementRecruiter.institution_id == institution_id)).all()
    if not rows:
        return None
    year = max(r.academic_year for r in rows)
    current = [r for r in rows if r.academic_year == year]
    return {
        "academic_year": year, "count": len(current), "companies": sorted({r.company_name for r in current}, key=str.lower),
        "note": "Listed by the institute. This doesn't show how many students a company hired, or from which branch.",
        "source_title": current[0].source_document.title, "source_url": current[0].source_document.url,
    }


def alumni_sample(db: Session, institution_id: int) -> dict | None:
    rows = db.scalars(select(AlumniObservation).options(joinedload(AlumniObservation.source_document)).where(AlumniObservation.institution_id == institution_id)).all()
    if not rows:
        return None
    by_dimension: dict[str, list[AlumniObservation]] = defaultdict(list)
    for row in rows:
        by_dimension[row.dimension].append(row)
    size = rows[0].sample_size
    source = {"source_title": rows[0].source_document.title, "source_url": rows[0].source_document.url, "retrieved_at": rows[0].source_document.fetched_at.date().isoformat()}
    if size < MIN_ALUMNI_SAMPLE:
        return {"status": "too_small", "sample_size": size, "minimum": MIN_ALUMNI_SAMPLE, "caveat": ALUMNI_CAVEAT, **source}
    top = lambda name: [{"label": r.category, "people": r.people} for r in sorted(by_dimension[name], key=lambda r: (-r.people, r.category))[:8]]  # noqa: E731
    founders = by_dimension["founder"][0].people if by_dimension["founder"] else 0
    return {"status": "available", "sample_size": size, "minimum": MIN_ALUMNI_SAMPLE, "founders": founders, "occupations": top("occupation"), "employers": top("employer"), "caveat": ALUMNI_CAVEAT, **source}


def career_profile(db: Session, institution_id: int) -> dict:
    return {
        "branch_outcomes": branch_outcomes(db, institution_id), "outcome_mix": outcome_mix(db, institution_id), "sectors": sectors(db, institution_id),
        "recruiters": recruiters(db, institution_id), "alumni": alumni_sample(db, institution_id),
        "not_available": "LinkedIn-style alumni data isn't collected, because scraping it isn't permitted.",
    }
