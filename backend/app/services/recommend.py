"""Build the shortlist from stored records. Deterministic, with no LLM in the ranking."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    CutoffRecord, FeeRecord, Institution, InstitutionRanking, PlacementRecord, Programme, QuotaEligibleState, RecommendationRun,
)
from app.schemas import StudentProfile
from app.services.bands import BAND_RANK, LOOKBACK_YEARS, CutoffPoint, classify
from app.services.branches import CAREER_BRANCH_AFFINITY, FAMILY_LABELS
from app.services.eligibility import exam_for, gender_pools, quota_applies, seat_claims
from app.services.scoring import ENGINE_VERSION, MIN_GRADUATING_CLASS, FitInputs, PlacementEvidence, career_score, quality_score, suitability_score

PAPER_FOR_EXAM = {"JEE_MAIN": "main_paper1", "JEE_ADVANCED": "advanced"}
POOL_LABEL = {"neutral": "Gender-neutral", "female": "Female-only"}


def latest_year(db: Session) -> int:
    return db.scalar(select(func.max(CutoffRecord.year)).where(CutoffRecord.is_final_round))


def career_goal_families(goals: list[str]) -> frozenset[str] | None:
    mapped = [CAREER_BRANCH_AFFINITY[g] for g in goals if g in CAREER_BRANCH_AFFINITY]
    return frozenset().union(*mapped) if mapped else None


def institution_evidence(db: Session) -> dict:
    """Load rankings, placements and fees once, to avoid a query per option."""
    rankings = {
        r.institution_id: r for r in db.scalars(
            select(InstitutionRanking).options(joinedload(InstitutionRanking.source))
            .where(InstitutionRanking.framework == "NIRF", InstitutionRanking.category == "Engineering")
            .order_by(InstitutionRanking.year)
        )
    }
    placements: dict[int, list[PlacementRecord]] = defaultdict(list)
    for record in db.scalars(select(PlacementRecord).options(joinedload(PlacementRecord.source_document))):
        placements[record.institution_id].append(record)
    fees: dict[int, FeeRecord] = {}
    for fee in db.scalars(select(FeeRecord).options(joinedload(FeeRecord.source_document)).order_by(FeeRecord.academic_year)):
        fees[fee.institution_id] = fee
    # One value per institute, per graduating year and per reporting definition, so unlike figures never mix.
    cohorts: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for records in placements.values():
        for record in latest_per_year(records):
            too_small = record.graduating_students is not None and record.graduating_students < MIN_GRADUATING_CLASS
            if record.median_salary_inr and not too_small:
                cohorts[(record.scope, record.reporting_definition)][record.graduation_year].append(float(record.median_salary_inr))
    return {"rankings": rankings, "placements": placements, "fees": fees, "cohorts": cohorts}


def latest_per_year(records: list[PlacementRecord]) -> list[PlacementRecord]:
    """A year can appear in several NIRF submissions. Keep the one from the newest document."""
    best: dict[tuple, PlacementRecord] = {}
    for record in sorted(records, key=lambda r: (r.source_document.reporting_year or 0, r.reporting_definition == "nirf_graduation_outcomes")):
        best[(record.programme_id, record.cohort_label, record.graduation_year)] = record
    return list(best.values())


def _evidence(records: list[PlacementRecord]) -> list[PlacementEvidence]:
    return [
        PlacementEvidence(r.scope, r.median_salary_inr, r.eligible_students, r.students_placed, r.graduation_year, r.reporting_definition, r.graduating_students)
        for r in records
    ]


def placement_view(programme_id: int, inst_id: int, evidence: dict) -> tuple[list[PlacementRecord], list[PlacementRecord]]:
    """Return this branch's own records, then the institute-wide ones. Both are shown, clearly separated."""
    all_records = evidence["placements"].get(inst_id, [])
    own = latest_per_year([r for r in all_records if r.programme_id == programme_id])
    institute = latest_per_year([r for r in all_records if r.scope == "institution"])
    return own, institute


def career_for(programme: Programme, evidence: dict) -> tuple[list[PlacementRecord], tuple[float | None, str, float]]:
    """All records to display, and the score. Institute reports aren't comparable, so branch figures alone aren't ranked yet."""
    own, institute = placement_view(programme.id, programme.institution_id, evidence)
    display = own + institute
    if own:
        scored = career_score(_evidence(own), evidence["cohorts"].get(("programme", own[0].reporting_definition), {}))
        if scored[0] is not None:
            return display, scored
    nirf = [r for r in institute if r.reporting_definition == "nirf_graduation_outcomes"] or [r for r in institute if r.reporting_definition.startswith("nirf_")]
    if not nirf:
        note = "Branch figures are shown but not scored, because institutes' reports use different definitions" if own else "Data not available"
        return display, (None, note, 0.0)
    if all(r.cohort_label.startswith("All 4-year") for r in nirf) and programme.duration_years != 4:
        return display, (None, f"Figures cover 4-year programmes only and this one lasts {programme.duration_years} years, so they aren't scored", 0.0)
    return display, career_score(_evidence(nirf), evidence["cohorts"].get((nirf[0].scope, nirf[0].reporting_definition), {}))


def best_salary_record(records: list[PlacementRecord]) -> PlacementRecord | None:
    """The newest median for this branch, or else the newest institute-wide one."""
    with_median = [r for r in records if r.median_salary_inr]
    branch = [r for r in with_median if r.scope == "programme"]
    return max(branch or with_median, key=lambda r: r.graduation_year, default=None)


def annual_cost(fee: FeeRecord | None) -> int | None:
    """Only a complete yearly cost can be compared with a budget. A partial sum would look cheaper."""
    if fee is None or None in (fee.annual_tuition_inr, fee.annual_hostel_inr, fee.annual_mess_inr):
        return None
    return fee.annual_tuition_inr + fee.annual_hostel_inr + fee.annual_mess_inr + (fee.annual_other_inr or 0)


def describe_quality(result) -> dict:
    return {
        "score": result.score, "coverage": result.coverage, "status": result.status,
        "components": [asdict(c) for c in result.components],
    }


def placement_json(records: list[PlacementRecord]) -> list[dict]:
    return [
        {
            "scope": r.scope,
            "scope_label": "This branch" if r.scope == "programme" else "Institute-wide, not specific to this branch",
            "cohort_label": r.cohort_label, "reporting_definition": r.reporting_definition,
            "graduation_year": r.graduation_year, "eligible_students": r.eligible_students,
            "graduating_students": r.graduating_students, "students_placed": r.students_placed, "total_students": r.total_students,
            "base_students": r.base_students, "base_label": r.base_label, "salary_basis": r.salary_basis,
            "higher_studies_students": r.higher_studies_students, "median_salary_inr": r.median_salary_inr,
            "average_salary_inr": r.average_salary_inr, "verification_status": r.verification_status,
            "notes": r.notes, "source_title": r.source_document.title, "source_url": r.source_document.url, "source_page": r.source_page,
        } for r in sorted(records, key=lambda x: (x.scope != "programme", x.reporting_definition, x.cohort_label, -x.graduation_year))
    ]


def ranking_json(ranking: InstitutionRanking | None) -> dict | None:
    if ranking is None:
        return None
    return {
        "framework": ranking.framework, "category": ranking.category, "year": ranking.year, "rank": ranking.rank,
        "score": float(ranking.score) if ranking.score is not None else None,
        "verification_status": ranking.verification_status, "source_name": ranking.source.name, "source_url": ranking.source.url,
    }


def fee_json(fee: FeeRecord | None) -> dict | None:
    if fee is None:
        return None
    return {
        "academic_year": fee.academic_year, "seat_type_group": fee.seat_type_group, "annual_complete_inr": annual_cost(fee),
        "annual_tuition_inr": fee.annual_tuition_inr, "annual_hostel_inr": fee.annual_hostel_inr,
        "annual_mess_inr": fee.annual_mess_inr, "annual_other_inr": fee.annual_other_inr, "one_time_inr": fee.one_time_inr,
        "refundable_deposit_inr": fee.refundable_deposit_inr, "payable_at_admission_inr": fee.payable_at_admission_inr,
        "verification_status": fee.verification_status, "notes": fee.notes, "source_title": fee.source_document.title,
        "source_url": fee.source_document.url, "source_page": fee.source_page,
    }


def data_gaps(placements: list, ranking, fee, quality_components) -> list[str]:
    gaps = []
    if not placements:
        gaps.append("No verified placement data")
    else:
        if all(p.scope == "institution" for p in placements):
            gaps.append("Placement data is institute-wide only, with nothing specific to this branch")
        gaps.append("Placement figures are self-reported and unaudited")
    if fee is None:
        gaps.append("No verified fee data")
    elif annual_cost(fee) is None:
        gaps.append("Fee record is partial, so a full yearly cost isn't available")
    if ranking is None:
        gaps.append("No NIRF rank on record")
    elif ranking.verification_status == "secondary_unverified":
        gaps.append("NIRF rank comes from a secondary source and is awaiting official verification")
    if any(c.key == "academic_faculty" and c.score is None for c in quality_components):
        gaps.append("Faculty and curriculum data not yet collected")
    return gaps


def _strengths_and_weaknesses(band, suitability, ranking) -> tuple[list[str], list[str]]:
    strengths, weaknesses = [], []
    for c in suitability.components:
        if c.score is None:
            continue
        if c.score >= 75 and c.key != "reputation":
            strengths.append(c.note)
        elif c.score <= 35:
            weaknesses.append(c.note)
    if ranking and ranking.rank <= 25:
        strengths.append(f"NIRF {ranking.year} Engineering rank {ranking.rank}")
    if band == "ambitious":
        weaknesses.append("Your rank is outside the recent closing range, so this needs cutoffs to move in your favour")
    elif band == "competitive":
        weaknesses.append("Close to recent closing ranks, so the outcome could go either way")
    return strengths, weaknesses


def generate(db: Session, profile: StudentProfile, per_band_limit: int = 25, record_run: bool = True) -> dict:
    student = profile.to_student()
    warnings: list[str] = [
        "Bands describe past cutoffs. They are not guarantees or probabilities, and future cutoffs can differ.",
        "This covers JoSAA only. CSAB special rounds and state counselling are not yet included.",
    ]
    if profile.class12_status == "does_not_meet":
        return {
            "engine_version": ENGINE_VERSION, "options": [], "counts": {},
            "warnings": warnings + [
                "JoSAA requires 75% in Class XII (65% for SC, ST and PwD) or a top-20-percentile board result, so no options are shown. Check Annexure 2 of the Business Rules with your board result."
            ],
        }
    if profile.class12_status == "unknown":
        warnings.append("Class XII criterion not confirmed: JoSAA needs 75% (65% for SC, ST and PwD) or a top-20-percentile board result.")
    if student.is_pwd:
        warnings.append("PwD seats depend on verified certificates. Institute-specific restrictions may also apply.")
    warnings.append("Some programmes have medical or other special restrictions. Check the JoSAA annexure for your programme.")

    data_year = latest_year(db)
    window_start = data_year - LOOKBACK_YEARS + 1
    pools = gender_pools(student)
    claims_by_exam = {exam: seat_claims(student, exam) for exam in ("JEE_MAIN", "JEE_ADVANCED")}
    quota_map: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in db.scalars(select(QuotaEligibleState)):
        quota_map[row.institution_id][row.quota].add(row.state)

    grouped: dict[tuple, list[CutoffRecord]] = defaultdict(list)
    programmes: dict[int, Programme] = {}
    for exam, claims in claims_by_exam.items():
        if not claims:
            continue
        lists = [c.rank_list for c in claims]
        query = (
            select(CutoffRecord).join(CutoffRecord.programme)
            .options(joinedload(CutoffRecord.programme).joinedload(Programme.institution))
            .where(
                CutoffRecord.is_final_round, CutoffRecord.year >= window_start, CutoffRecord.rank_list.in_(lists),
                CutoffRecord.gender_pool.in_(pools), CutoffRecord.is_preparatory.is_(False),
                CutoffRecord.closing_rank.is_not(None), Programme.required_paper == PAPER_FOR_EXAM[exam],
            )
        )
        for record in db.scalars(query):
            programmes[record.programme_id] = record.programme
            grouped[(record.programme_id, record.quota, record.seat_type, record.gender_pool)].append(record)

    routes: dict[int, list[dict]] = defaultdict(list)
    for (programme_id, quota, seat_type, pool), records in grouped.items():
        programme = programmes[programme_id]
        inst = programme.institution
        exam = exam_for(inst.institute_type)
        claim = next((c for c in claims_by_exam[exam] if c.seat_type == seat_type), None)
        if claim is None or claim.rank_list != records[0].rank_list:
            continue
        applies, quota_reason = quota_applies(quota, student.eligibility_state, inst.institute_type, quota_map[inst.id])
        if not applies:
            continue
        result = classify(claim.rank, [CutoffPoint(r.year, r.closing_rank) for r in records], data_year)
        routes[programme_id].append({
            "quota": quota, "seat_type": seat_type, "gender_pool": pool, "gender_pool_label": POOL_LABEL[pool],
            "rank_used": claim.rank, "rank_list": claim.rank_list, "band": result.band,
            "low_closing": result.low_closing, "high_closing": result.high_closing,
            "latest_year": result.latest_year, "latest_closing": result.latest_closing,
            "years_used": list(result.years_used), "explanation": result.explanation, "quota_reason": quota_reason,
        })

    evidence = institution_evidence(db)
    goals = career_goal_families(profile.career_goals)
    avoided = set(profile.avoid_branches)
    options = []
    excluded = {"avoided_branch": 0, "beyond_range": 0}
    for programme_id, seat_routes in routes.items():
        programme = programmes[programme_id]
        inst = programme.institution
        if programme.branch_family in avoided:
            excluded["avoided_branch"] += 1
            continue
        banded = [r for r in seat_routes if r["band"] is not None]
        best = min(
            banded or seat_routes,
            key=lambda r: (BAND_RANK.get(r["band"], 9), r["rank_used"] / (r["high_closing"] or r["latest_closing"] or 1), r["quota"], r["seat_type"], r["gender_pool"]),
        )
        if best["band"] == "beyond":
            excluded["beyond_range"] += 1
            continue
        ranking = evidence["rankings"].get(inst.id)
        fee = evidence["fees"].get(inst.id)
        placement_records, career = career_for(programme, evidence)
        note = (
            f"NIRF {ranking.year} rank {ranking.rank} ({ranking.verification_status.replace('_', ' ')})" if ranking else ""
        )
        quality = quality_score(ranking.rank if ranking else None, note, career)
        suitability = suitability_score(FitInputs(
            branch_family=programme.branch_family, institute_type=inst.institute_type, state=inst.state,
            nirf_rank=ranking.rank if ranking else None, career_dimension_score=career[0], annual_cost_inr=annual_cost(fee),
            preferred_branches=frozenset(profile.preferred_branches), acceptable_branches=frozenset(profile.acceptable_branches),
            career_goal_families=goals, preferred_states=frozenset(profile.preferred_states),
            preferred_types=frozenset(profile.preferred_types), annual_budget_inr=profile.annual_budget_inr,
            career_note=career[1], priorities=profile.priorities,
        ))
        strengths, weaknesses = _strengths_and_weaknesses(best["band"], suitability, ranking)
        options.append({
            "programme_id": programme.id, "programme": programme.name, "degree": programme.degree,
            "duration_years": programme.duration_years, "branch_family": programme.branch_family,
            "branch_label": FAMILY_LABELS.get(programme.branch_family, "Other"),
            "institution": {"slug": inst.slug, "short_name": inst.short_name, "official_name": inst.official_name, "type": inst.institute_type, "city": inst.city, "state": inst.state},
            "band": best["band"], "best_route": best,
            "other_routes": sorted([r for r in seat_routes if r is not best], key=lambda r: (BAND_RANK.get(r["band"], 9), r["quota"], r["seat_type"], r["gender_pool"])),
            "quality": describe_quality(quality),
            "suitability": {"score": suitability.score, "coverage": suitability.coverage, "components": [asdict(c) for c in suitability.components]},
            "ranking": ranking_json(ranking), "placements": placement_json(placement_records), "fee": fee_json(fee),
            "strengths": strengths, "weaknesses": weaknesses,
            "data_gaps": data_gaps(placement_records, ranking, fee, quality.components),
            "why": [best["explanation"], best["quota_reason"]] + [c.note for c in suitability.components if c.score is not None and c.score >= 75],
        })

    options.sort(key=lambda o: (-(o["suitability"]["score"] or 0), BAND_RANK.get(o["band"], 9), o["institution"]["short_name"], o["programme"], o["programme_id"]))
    counts: dict[str, int] = defaultdict(int)
    limited = []
    for option in options:
        band = option["band"] or "limited_history"
        counts[band] += 1
        if counts[band] <= per_band_limit:
            limited.append(option)

    payload = {
        "engine_version": ENGINE_VERSION, "data_year": data_year, "history_window": [window_start, data_year],
        "counts": dict(counts), "excluded": excluded, "warnings": warnings, "options": limited,
    }
    if record_run:
        snapshot = profile.model_dump()
        input_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        identity = [(o["programme_id"], o["band"], o["suitability"]["score"]) for o in limited]
        result_hash = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        if not settings.read_only:
            db.add(RecommendationRun(engine_version=ENGINE_VERSION, input_hash=input_hash, input_snapshot=snapshot, result_count=len(limited), result_hash=result_hash))
            db.commit()
        payload["result_hash"] = result_hash
    return payload
