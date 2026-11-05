from __future__ import annotations

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import CutoffRecord, DataSource, FeeRecord, Institution, InstitutionAlias, InstitutionRanking, PlacementRecord, Programme, SourceDocument
from app.schemas import STATES, ComparisonRequest, ParentReportRequest, PreferenceListRequest, RecommendationRequest, RoiRequest
from app.services import careers, finance, preferences, report
from app.services import recommend as rec
from app.services.branches import CAREER_BRANCH_AFFINITY, FAMILY_LABELS
from app.services.comparison import compare
from app.services.scoring import DEFAULT_PRIORITIES, ENGINE_VERSION, QUALITY_LABELS, QUALITY_WEIGHTS, SUITABILITY_LABELS

router = APIRouter(prefix="/api/v1")

CAREER_OPTIONS = {
    "software": "Software engineering", "ai_ml": "AI and machine learning", "core": "Core engineering",
    "electronics": "Electronics and semiconductor", "research": "Research", "higher_studies": "Higher studies",
    "consulting": "Consulting", "finance": "Finance", "entrepreneurship": "Entrepreneurship",
    "government": "Government jobs", "undecided": "Undecided",
}


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok", "cutoff_rows": db.scalar(select(func.count()).select_from(CutoffRecord))}


@router.get("/meta")
def meta(db: Session = Depends(get_db)) -> dict:
    return {
        "states": STATES, "branch_families": FAMILY_LABELS, "career_options": CAREER_OPTIONS,
        "career_mapped": sorted(CAREER_BRANCH_AFFINITY), "default_priorities": DEFAULT_PRIORITIES,
        "suitability_labels": SUITABILITY_LABELS, "quality_labels": QUALITY_LABELS, "quality_weights": QUALITY_WEIGHTS,
        "latest_data_year": rec.latest_year(db), "engine_version": ENGINE_VERSION,
        "institute_types": {"IIT": "IIT", "IISC": "IISc", "NIT": "NIT", "IIIT": "IIIT", "GFTI": "Other government-funded (GFTI)"},
    }


def _institution_completeness(inst: Institution, has_cutoffs: bool, has_placements: bool, has_fees: bool) -> dict:
    fields = {
        "cutoffs": has_cutoffs, "nirf_rank": bool(inst.rankings), "placements": has_placements, "fees": has_fees,
        "website": bool(inst.website), "location_verified": inst.location_verification == "verified",
    }
    return {"fields": fields, "percent": round(100 * sum(fields.values()) / len(fields))}


@router.get("/institutions")
def list_institutions(
    q: str | None = Query(None, max_length=120), type: str | None = None, state: str | None = None,
    branch: str | None = None, pilot: bool | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100), db: Session = Depends(get_db),
) -> dict:
    query = select(Institution).options(selectinload(Institution.rankings).joinedload(InstitutionRanking.source))
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            Institution.short_name.ilike(like), Institution.official_name.ilike(like), Institution.city.ilike(like),
            Institution.id.in_(select(InstitutionAlias.institution_id).where(InstitutionAlias.alias.ilike(like))),
        ))
    if type:
        query = query.where(Institution.institute_type == type)
    if state:
        query = query.where(Institution.state == state)
    if pilot is not None:
        query = query.where(Institution.is_pilot == pilot)
    if branch:
        query = query.where(Institution.id.in_(select(Programme.institution_id).where(Programme.branch_family == branch)))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    # Order by recorded NIRF rank where present, then name. Unranked does not imply worse.
    best_rank = select(InstitutionRanking.institution_id, func.min(InstitutionRanking.rank).label("r")).group_by(InstitutionRanking.institution_id).subquery()
    rows = db.scalars(
        query.outerjoin(best_rank, best_rank.c.institution_id == Institution.id)
        .order_by(best_rank.c.r.asc().nulls_last(), Institution.short_name).offset((page - 1) * page_size).limit(page_size)
    ).all()
    ids = [i.id for i in rows]
    programme_counts = dict(db.execute(select(Programme.institution_id, func.count()).where(Programme.institution_id.in_(ids)).group_by(Programme.institution_id)).all())
    placements = set(db.scalars(select(distinct(PlacementRecord.institution_id)).where(PlacementRecord.institution_id.in_(ids))))
    fees = set(db.scalars(select(distinct(FeeRecord.institution_id)).where(FeeRecord.institution_id.in_(ids))))
    items = []
    for inst in rows:
        ranking = max(inst.rankings, key=lambda r: r.year, default=None)
        items.append({
            "slug": inst.slug, "short_name": inst.short_name, "official_name": inst.official_name, "type": inst.institute_type,
            "city": inst.city, "state": inst.state, "is_pilot": inst.is_pilot, "programme_count": programme_counts.get(inst.id, 0),
            "ranking": rec.ranking_json(ranking),
            "completeness": _institution_completeness(inst, programme_counts.get(inst.id, 0) > 0, inst.id in placements, inst.id in fees),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/institutions/{slug}")
def get_institution(slug: str, db: Session = Depends(get_db)) -> dict:
    inst = db.scalar(
        select(Institution).where(Institution.slug == slug)
        .options(selectinload(Institution.aliases), selectinload(Institution.rankings).joinedload(InstitutionRanking.source), selectinload(Institution.quota_states))
    )
    if inst is None:
        raise HTTPException(404, "Institution not found")
    programmes = db.scalars(select(Programme).where(Programme.institution_id == inst.id).order_by(Programme.name)).all()
    years = dict(db.execute(
        select(CutoffRecord.programme_id, func.max(CutoffRecord.year))
        .where(CutoffRecord.programme_id.in_([p.id for p in programmes])).group_by(CutoffRecord.programme_id)
    ).all())
    latest = rec.latest_year(db)
    placements = rec.latest_per_year(list(db.scalars(select(PlacementRecord).options(joinedload(PlacementRecord.source_document)).where(PlacementRecord.institution_id == inst.id, PlacementRecord.scope == "institution"))))
    fees = db.scalars(select(FeeRecord).options(joinedload(FeeRecord.source_document)).where(FeeRecord.institution_id == inst.id).order_by(FeeRecord.academic_year.desc())).all()
    quota_states: dict[str, list[str]] = defaultdict(list)
    for row in inst.quota_states:
        quota_states[row.quota].append(row.state)
    return {
        "slug": inst.slug, "short_name": inst.short_name, "official_name": inst.official_name, "type": inst.institute_type,
        "city": inst.city, "state": inst.state, "website": inst.website, "is_pilot": inst.is_pilot,
        "location_verification": inst.location_verification,
        "aliases": sorted(a.alias for a in inst.aliases if a.alias != inst.official_name),
        "rankings": [rec.ranking_json(r) for r in sorted(inst.rankings, key=lambda r: -r.year)],
        "quota_states": {k: sorted(v) for k, v in quota_states.items()},
        "institution_placements": rec.placement_json(list(placements)),
        "fee": rec.fee_json(fees[0] if fees else None),
        "programmes": [
            {
                "id": p.id, "name": p.name, "degree": p.degree, "duration_years": p.duration_years, "branch_family": p.branch_family,
                "branch_label": FAMILY_LABELS.get(p.branch_family, "Other"), "last_seen_year": years.get(p.id),
                "currently_offered": years.get(p.id) == latest,
            } for p in programmes
        ],
        "completeness": _institution_completeness(inst, bool(programmes), bool(placements), bool(fees)),
        "careers": careers.career_profile(db, inst.id),
    }


@router.get("/programmes/{programme_id}")
def get_programme(programme_id: int, db: Session = Depends(get_db)) -> dict:
    programme = db.scalar(select(Programme).where(Programme.id == programme_id).options(joinedload(Programme.institution)))
    if programme is None:
        raise HTTPException(404, "Programme not found")
    inst = programme.institution
    seats = db.execute(
        select(CutoffRecord.seat_type, CutoffRecord.quota, CutoffRecord.gender_pool).where(CutoffRecord.programme_id == programme_id).distinct()
    ).all()
    evidence = rec.institution_evidence(db)
    records, _ = rec.career_for(programme, evidence)
    return {
        "id": programme.id, "name": programme.name, "degree": programme.degree, "duration_years": programme.duration_years,
        "branch_family": programme.branch_family, "branch_label": FAMILY_LABELS.get(programme.branch_family, "Other"),
        "required_paper": programme.required_paper,
        "institution": {"slug": inst.slug, "short_name": inst.short_name, "official_name": inst.official_name, "type": inst.institute_type, "city": inst.city, "state": inst.state},
        "available_seats": [{"seat_type": s, "quota": q, "gender_pool": g} for s, q, g in sorted(seats)],
        "placements": rec.placement_json(records), "ranking": rec.ranking_json(evidence["rankings"].get(inst.id)),
        "fee": rec.fee_json(evidence["fees"].get(inst.id)),
        "curriculum": None, "faculty": None,
    }


@router.get("/programmes/{programme_id}/cutoffs")
def programme_cutoffs(
    programme_id: int, seat_type: str = "OPEN", quota: str | None = None,
    gender_pool: Literal["neutral", "female"] = "neutral", db: Session = Depends(get_db),
) -> dict:
    query = (
        select(CutoffRecord).options(joinedload(CutoffRecord.source_document))
        .where(CutoffRecord.programme_id == programme_id, CutoffRecord.seat_type == seat_type, CutoffRecord.gender_pool == gender_pool)
        .order_by(CutoffRecord.quota, CutoffRecord.year, CutoffRecord.round)
    )
    if quota:
        query = query.where(CutoffRecord.quota == quota)
    records = db.scalars(query).all()
    return {
        "programme_id": programme_id, "seat_type": seat_type, "gender_pool": gender_pool,
        "note": "Historical closing ranks only. These are not admission probabilities. Ranks are on the list named in rank_list.",
        "records": [
            {
                "year": r.year, "round": r.round, "is_final_round": r.is_final_round, "quota": r.quota, "rank_list": r.rank_list,
                "opening_rank": r.opening_rank, "closing_rank": r.closing_rank, "is_preparatory": r.is_preparatory,
                "raw_closing": r.raw_closing, "source_title": r.source_document.title, "source_url": r.source_document.url,
                "fetched_at": r.source_document.fetched_at.isoformat(),
            } for r in records
        ],
    }


@router.get("/programmes/{programme_id}/placements")
def programme_placements(programme_id: int, db: Session = Depends(get_db)) -> dict:
    programme = db.get(Programme, programme_id)
    if programme is None:
        raise HTTPException(404, "Programme not found")
    records, _ = rec.career_for(programme, rec.institution_evidence(db))
    return {"programme_id": programme_id, "records": rec.placement_json(records), "status": "available" if records else "Data not available"}


@router.post("/recommendations/generate")
def generate_recommendations(body: RecommendationRequest, db: Session = Depends(get_db)) -> dict:
    return rec.generate(db, body.profile, body.per_band_limit)


@router.post("/comparisons")
def create_comparison(body: ComparisonRequest, db: Session = Depends(get_db)) -> dict:
    if len(set(body.programme_ids)) != len(body.programme_ids):
        raise HTTPException(422, "Choose different programmes to compare")
    result = compare(db, body.programme_ids, body.profile)
    if result is None:
        raise HTTPException(404, "One or more programmes were not found")
    return result


@router.post("/preference-lists/analyse")
def analyse_preference_list(body: PreferenceListRequest, db: Session = Depends(get_db)) -> dict:
    return preferences.analyse(db, body.profile, body.programme_ids)


@router.post("/reports/parent")
def parent_report(body: ParentReportRequest, db: Session = Depends(get_db)) -> dict:
    result = report.build(db, body.profile, body.programme_ids)
    if result is None:
        raise HTTPException(404, "One or more programmes were not found")
    return result


@router.get("/financial/defaults/{programme_id}")
def financial_defaults(programme_id: int, db: Session = Depends(get_db)) -> dict:
    programme = db.scalar(select(Programme).where(Programme.id == programme_id).options(joinedload(Programme.institution)))
    if programme is None:
        raise HTTPException(404, "Programme not found")
    evidence = rec.institution_evidence(db)
    records, _ = rec.career_for(programme, evidence)
    salary = rec.best_salary_record(records)
    return {
        "programme_id": programme.id, "programme": programme.name, "institution": programme.institution.short_name, "years": programme.duration_years,
        "fee": rec.fee_json(evidence["fees"].get(programme.institution_id)),
        "median": rec.placement_json([salary])[0] if salary else None,
    }


@router.post("/financial/roi")
def financial_roi(body: RoiRequest) -> dict:
    costs = finance.total_cost(finance.CostInputs(
        body.annual_tuition_inr, body.annual_hostel_inr, body.annual_mess_inr, body.annual_other_inr, body.one_time_inr,
        body.refundable_deposit_inr, body.annual_living_inr, body.annual_scholarship_inr, body.years,
    ))
    funding_gap = max(0, costs["total_cost"] - body.family_contribution_inr)
    amount = body.loan_amount_inr if body.loan_amount_inr is not None else funding_gap
    loan = finance.loan(amount, body.interest_rate_percent, body.repayment_years, body.moratorium_months)
    salaries = finance.salary_scenarios(body.median_ctc_inr, body.low_ctc_inr, body.high_ctc_inr)
    payback_on = loan["total_repaid"] + max(0, costs["total_excluding_refundable"] - amount)
    scenarios = [
        finance.scenario(name, ctc, body.take_home_share, body.repayment_share, loan["monthly_emi"], payback_on) for name, ctc in salaries.items()
    ] if salaries else []
    return {
        "costs": costs, "funding_gap": funding_gap, "loan": loan, "scenarios": scenarios,
        "assumptions": {
            "low_factor": finance.LOW_FACTOR, "high_factor": finance.HIGH_FACTOR, "take_home_share": body.take_home_share, "repayment_share": body.repayment_share,
            "low_is_assumed": body.low_ctc_inr is None, "high_is_assumed": body.high_ctc_inr is None,
        },
        "warning": "This is an estimate and not a guaranteed return. Salaries vary, and the median is for placed students only. Costs change every year. Check loan terms with your lender.",
    }


@router.get("/data/sources")
def data_sources(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(DataSource).order_by(DataSource.tier, DataSource.name)).all()
    docs = dict(db.execute(select(SourceDocument.source_id, func.count()).group_by(SourceDocument.source_id)).all())
    return {"sources": [
        {
            "key": s.key, "name": s.name, "publisher": s.publisher, "url": s.url, "tier": s.tier, "access_method": s.access_method,
            "access_status": s.access_status, "terms_note": s.terms_note, "documents": docs.get(s.id, 0),
            "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        } for s in rows
    ]}


@router.get("/data/completeness")
def data_completeness(db: Session = Depends(get_db)) -> dict:
    count = lambda model: db.scalar(select(func.count()).select_from(model))  # noqa: E731
    institutions = count(Institution)
    with_col = lambda col: db.scalar(select(func.count(distinct(col))))  # noqa: E731
    return {
        "institutions": institutions, "programmes": count(Programme), "cutoff_records": count(CutoffRecord),
        "cutoff_years": sorted(db.scalars(select(distinct(CutoffRecord.year)))),
        "coverage": {
            "cutoffs": with_col(Programme.institution_id), "nirf_rank": with_col(InstitutionRanking.institution_id),
            "placements": with_col(PlacementRecord.institution_id), "fees": with_col(FeeRecord.institution_id),
            "location_verified": db.scalar(select(func.count()).select_from(Institution).where(Institution.location_verification == "verified")),
        },
        "not_yet_collected": ["Faculty", "Curriculum", "Seat matrix", "CSAB and state counselling", "Verified alumni outcomes"],
    }
