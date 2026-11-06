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
    CsabCutoff, CutoffRecord, FeeRecord, Institution, InstitutionRanking, PlacementRecord, Programme, QuotaEligibleState, RecommendationRun,
    SeatMatrixRecord,
)
from app.schemas import StudentProfile
from app.services.bands import BAND_RANK, LOOKBACK_YEARS, CutoffPoint, classify
from app.services.branches import CAREER_BRANCH_AFFINITY, FAMILY_LABELS
from app.services.eligibility import exam_for, gender_pools, quota_applies, seat_claims
from app.services.scoring import ENGINE_VERSION, MIN_GRADUATING_CLASS, FitInputs, PlacementEvidence, career_score, contest_scores, quality_score, suitability_score

PAPER_FOR_EXAM = {"JEE_MAIN": "main_paper1", "JEE_ADVANCED": "advanced"}
POOL_LABEL = {"neutral": "Gender-neutral", "female": "Female-only"}
CONTEST_GROUP = {"JEE_MAIN": "NIT, IIIT and GFTI programmes", "JEE_ADVANCED": "IIT and IISc programmes"}


def latest_year(db: Session) -> int:
    return db.scalar(select(func.max(CutoffRecord.year)).where(CutoffRecord.is_final_round))


def offered_programmes(db: Session, data_year: int) -> set[int]:
    """Programmes in the latest seat matrix, or with a final-round cutoff that year if no matrix is loaded."""
    listed = set(db.scalars(select(SeatMatrixRecord.programme_id).where(SeatMatrixRecord.year == data_year).distinct()))
    return listed or set(db.scalars(select(CutoffRecord.programme_id).where(CutoffRecord.is_final_round, CutoffRecord.year == data_year).distinct()))


def lineage_map(db: Session) -> dict[int, int]:
    """Earlier programme id to its latest name's id, from the reviewed list of renames."""
    successors = dict(db.execute(select(Programme.id, Programme.successor_id).where(Programme.successor_id.is_not(None))).all())
    resolved = {}
    for earlier in successors:
        latest = successors[earlier]
        while latest in successors:
            latest = successors[latest]
        resolved[earlier] = latest
    return resolved


def history_ids(lineage: dict[int, int], programme_id: int) -> list[int]:
    """This programme's id with the ids of its earlier names."""
    return [programme_id] + [earlier for earlier, latest in lineage.items() if latest == programme_id]


def earlier_names(db: Session, lineage: dict[int, int], programme_id: int) -> list[dict]:
    ids = [i for i in history_ids(lineage, programme_id) if i != programme_id]
    if not ids:
        return []
    rows = db.execute(
        select(Programme.name, func.max(CutoffRecord.year)).join(CutoffRecord, CutoffRecord.programme_id == Programme.id)
        .where(Programme.id.in_(ids)).group_by(Programme.id, Programme.name)
    ).all()
    return [{"name": name, "until": year} for name, year in sorted(rows, key=lambda r: r[1])]


def seat_view(db: Session, year: int) -> dict[tuple, int]:
    rows = db.execute(select(SeatMatrixRecord.programme_id, SeatMatrixRecord.quota, SeatMatrixRecord.seat_type, SeatMatrixRecord.gender_pool, SeatMatrixRecord.seats).where(SeatMatrixRecord.year == year))
    return {(p, q, t, g): seats for p, q, t, g, seats in rows}


def location_of(programme: Programme) -> tuple[str | None, str]:
    """Where the programme runs. A campus abroad reports its own city and country, not the parent institute's."""
    if programme.campus_city:
        return programme.campus_city, programme.campus_country or programme.institution.state
    return programme.institution.city, programme.institution.state


def institution_json(programme: Programme, full: bool = True) -> dict:
    inst = programme.institution
    city, state = location_of(programme)
    out = {"slug": inst.slug, "short_name": inst.short_name, "type": inst.institute_type, "city": city, "state": state}
    if full:
        out["official_name"] = inst.official_name
    if programme.campus_city:
        out["campus_note"] = f"Runs on {inst.short_name}'s campus in {programme.campus_city}, {programme.campus_country}. {inst.short_name}'s rank, fees and institute-wide placements describe its main campus, so they aren't applied here."
    return out


def ranking_for(programme: Programme, evidence: dict) -> InstitutionRanking | None:
    return None if programme.campus_city else evidence["rankings"].get(programme.institution_id)


def fee_for(programme: Programme, evidence: dict) -> FeeRecord | None:
    return None if programme.campus_city else evidence["fees"].get(programme.institution_id)


def cost_inputs(fee: FeeRecord | None, profile: StudentProfile) -> dict:
    """What can be compared with a budget. Fee records state who they cover, and aren't applied to anyone else."""
    if fee is None:
        return {"annual_cost_inr": None}
    if "General/OBC-NCL/EWS" in (fee.seat_type_group or "") and (profile.category in ("SC", "ST") or profile.is_pwd):
        return {"annual_cost_inr": None, "cost_note": "The fee on record is for General, OBC-NCL and EWS students. SC, ST and PwD students usually pay no tuition, so check with the institute"}
    return {"annual_cost_inr": annual_cost(fee), "annual_known_inr": known_annual_charges(fee)}


def contest_view(db: Session, data_year: int) -> dict[int, tuple[float, str]]:
    """How contested each programme is, within its own exam, using OPEN gender-neutral seats open to candidates from anywhere."""
    rows = db.execute(
        select(CutoffRecord.programme_id, CutoffRecord.closing_rank, Institution.institute_type)
        .join(CutoffRecord.programme).join(Programme.institution)
        .where(
            CutoffRecord.is_final_round, CutoffRecord.year > data_year - LOOKBACK_YEARS, CutoffRecord.seat_type == "OPEN",
            CutoffRecord.gender_pool == "neutral", CutoffRecord.quota.in_(("AI", "OS")), CutoffRecord.is_preparatory.is_(False),
            CutoffRecord.closing_rank.is_not(None), Programme.required_paper.in_(PAPER_FOR_EXAM.values()),
        )
    )
    offered = offered_programmes(db, data_year)
    lineage = lineage_map(db)
    closings: dict[str, dict[int, list[int]]] = {exam: defaultdict(list) for exam in PAPER_FOR_EXAM}
    for programme_id, closing, institute_type in rows:
        programme_id = lineage.get(programme_id, programme_id)
        if programme_id in offered:
            closings[exam_for(institute_type)][programme_id].append(closing)
    view = {}
    for exam, by_programme in closings.items():
        for programme_id, score in contest_scores({p: sum(v) / len(v) for p, v in by_programme.items()}).items():
            view[programme_id] = (score, f"More contested than about {round(score)}% of {CONTEST_GROUP[exam]}. This reflects past candidates' choices, not quality")
    return view


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
    if programme.campus_city:
        institute = []
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


def known_annual_charges(fee: FeeRecord | None) -> int | None:
    """Yearly charges the record does state. A minimum, so it can only show that a budget is exceeded."""
    if fee is None:
        return None
    parts = [fee.annual_tuition_inr, fee.annual_hostel_inr, fee.annual_mess_inr, fee.annual_other_inr]
    return sum(p for p in parts if p is not None) if fee.annual_tuition_inr is not None else None


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
        "annual_known_inr": known_annual_charges(fee),
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
        elif c.score <= 35 and c.key != "demand":
            weaknesses.append(c.note)
    if ranking and ranking.rank <= 25:
        strengths.append(f"NIRF {ranking.year} Engineering rank {ranking.rank}")
    if band == "ambitious":
        weaknesses.append("Your rank is outside the recent closing range, so this needs cutoffs to move in your favour")
    elif band == "competitive":
        weaknesses.append("Close to recent closing ranks, so the outcome could go either way")
    return strengths, weaknesses


def fit_contest(contest: dict[int, tuple[float, str]], programme_id: int) -> dict:
    score, note = contest.get(programme_id, (None, None))
    return {"demand_score": score, "demand_note": note} if note else {}


CSAB_NOTE = (
    "CSAB special rounds offer seats left vacant after JoSAA, at NITs, IIITs and GFTIs only. These are the 2026 closing ranks, "
    "on the common rank list, for one year only, so they have no bands and vacancies change every year. "
    "Registration and eligibility rules differ from JoSAA, so check csab.nic.in before relying on this."
)
CSAB_LIMIT = 30


def csab_leads(db: Session, profile: StudentProfile, student, quota_map: dict) -> dict | None:
    """Programmes whose special round closed at or beyond this student's rank. A lead to check, kept apart from the shortlist."""
    rank = student.main.crl
    claims = seat_claims(student, "JEE_MAIN")
    if rank is None or not claims:
        return None
    avoided = set(profile.avoid_branches)
    preferred, acceptable = set(profile.preferred_branches), set(profile.acceptable_branches)
    best: dict[int, CsabCutoff] = {}
    query = (
        select(CsabCutoff).join(CsabCutoff.programme)
        .options(joinedload(CsabCutoff.programme).joinedload(Programme.institution), joinedload(CsabCutoff.source_document))
        .where(
            CsabCutoff.closing_rank >= rank, CsabCutoff.seat_type.in_([c.seat_type for c in claims]),
            CsabCutoff.gender_pool.in_(gender_pools(student)), Programme.required_paper == PAPER_FOR_EXAM["JEE_MAIN"],
        )
    )
    for row in db.scalars(query):
        inst = row.programme.institution
        if row.programme.branch_family in avoided or not quota_applies(row.quota, student.eligibility_state, inst.institute_type, quota_map[inst.id])[0]:
            continue
        current = best.get(row.programme_id)
        if current is None or (row.round, row.closing_rank) > (current.round, current.closing_rank):
            best[row.programme_id] = row
    def order(row: CsabCutoff) -> tuple:
        family = row.programme.branch_family
        return (0 if family in preferred else 1 if family in acceptable else 2, row.closing_rank, row.programme_id)
    rows = sorted(best.values(), key=order)
    return {
        "count": len(rows), "rank_used": rank, "note": CSAB_NOTE,
        "options": [
            {
                "programme_id": r.programme_id, "programme": r.programme.name, "degree": r.programme.degree, "branch_label": FAMILY_LABELS.get(r.programme.branch_family, "Other"),
                "institution": institution_json(r.programme, full=False), "year": r.year, "round": r.round, "quota": r.quota, "seat_type": r.seat_type,
                "gender_pool_label": POOL_LABEL[r.gender_pool], "closing_rank": r.closing_rank, "source_title": r.source_document.title, "source_url": r.source_document.url,
            } for r in rows[:CSAB_LIMIT]
        ],
    }


def generate(db: Session, profile: StudentProfile, per_band_limit: int = 25, record_run: bool = True) -> dict:
    student = profile.to_student()
    warnings: list[str] = [
        "Bands describe past cutoffs. They are not guarantees or probabilities, and future cutoffs can differ.",
        "Bands cover JoSAA only. CSAB special round ranks are listed separately, without bands. State counselling is not included.",
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
    lineage = lineage_map(db)
    programmes = {p.id: p for p in db.scalars(select(Programme).options(joinedload(Programme.institution)))}
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
            grouped[(lineage.get(record.programme_id, record.programme_id), record.quota, record.seat_type, record.gender_pool)].append(record)

    seats = seat_view(db, data_year)
    total_seats: dict[int, int] = defaultdict(int)
    for key, count in seats.items():
        total_seats[key[0]] += count
    renamed = defaultdict(list)
    for earlier, latest in lineage.items():
        renamed[latest].append(earlier)
    no_seat_now: set[int] = set()
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
        seat_count = seats.get((programme_id, quota, seat_type, pool))
        # Past cutoffs can't help if this year's matrix has no such seat. A filled seat with a cutoff always stays.
        if seat_count == 0 and result.latest_year != data_year:
            no_seat_now.add(programme_id)
            continue
        routes[programme_id].append({
            "quota": quota, "seat_type": seat_type, "gender_pool": pool, "gender_pool_label": POOL_LABEL[pool], "seats": seat_count,
            "rank_used": claim.rank, "rank_list": claim.rank_list, "band": result.band,
            "low_closing": result.low_closing, "high_closing": result.high_closing,
            "latest_year": result.latest_year, "latest_closing": result.latest_closing,
            "years_used": list(result.years_used), "explanation": result.explanation, "quota_reason": quota_reason,
        })

    evidence = institution_evidence(db)
    goals = career_goal_families(profile.career_goals)
    avoided = set(profile.avoid_branches)
    options = []
    excluded = {"avoided_branch": 0, "beyond_range": 0, "no_latest_cutoff": 0, "no_seat_in_category": len(no_seat_now - routes.keys())}
    offered = offered_programmes(db, data_year)
    contest = contest_view(db, data_year)
    for programme_id, seat_routes in routes.items():
        programme = programmes[programme_id]
        inst = programme.institution
        if programme.branch_family in avoided:
            excluded["avoided_branch"] += 1
            continue
        within_reach = [r for r in seat_routes if r["band"] != "beyond"]
        if not within_reach:
            excluded["beyond_range"] += 1
            continue
        if programme_id not in offered:
            excluded["no_latest_cutoff"] += 1
            continue
        banded = [r for r in within_reach if r["band"] is not None]
        best = min(
            banded or within_reach,
            key=lambda r: (BAND_RANK.get(r["band"], 9), r["rank_used"] / (r["high_closing"] or r["latest_closing"] or 1), r["quota"], r["seat_type"], r["gender_pool"]),
        )
        ranking = ranking_for(programme, evidence)
        fee = fee_for(programme, evidence)
        placement_records, career = career_for(programme, evidence)
        note = (
            f"NIRF {ranking.year} rank {ranking.rank} ({ranking.verification_status.replace('_', ' ')})" if ranking else ""
        )
        quality = quality_score(ranking.rank if ranking else None, note, career)
        suitability = suitability_score(FitInputs(
            branch_family=programme.branch_family, institute_type=inst.institute_type, state=location_of(programme)[1],
            nirf_rank=ranking.rank if ranking else None, career_dimension_score=career[0], **cost_inputs(fee, profile),
            preferred_branches=frozenset(profile.preferred_branches), acceptable_branches=frozenset(profile.acceptable_branches),
            career_goal_families=goals, preferred_states=frozenset(profile.preferred_states),
            preferred_types=frozenset(profile.preferred_types), annual_budget_inr=profile.annual_budget_inr,
            career_note=career[1], priorities=profile.priorities,
            **fit_contest(contest, programme_id),
        ))
        strengths, weaknesses = _strengths_and_weaknesses(best["band"], suitability, ranking)
        if best["seats"] is not None and 0 < best["seats"] <= 2:
            weaknesses.append(f"Only {best['seats']} seat{'s' if best['seats'] > 1 else ''} in this category in {data_year}, so one candidate's choice can move the closing rank a long way")
        options.append({
            "programme_id": programme.id, "programme": programme.name, "degree": programme.degree,
            "duration_years": programme.duration_years, "branch_family": programme.branch_family,
            "branch_label": FAMILY_LABELS.get(programme.branch_family, "Other"),
            "institution": institution_json(programme), "earlier_names": earlier_names(db, lineage, programme.id) if programme.id in renamed else [],
            "total_seats": total_seats.get(programme.id),
            "band": best["band"], "best_route": best,
            "other_routes": sorted([r for r in seat_routes if r is not best], key=lambda r: (BAND_RANK.get(r["band"], 9), r["quota"], r["seat_type"], r["gender_pool"])),
            "quality": describe_quality(quality),
            "suitability": {"score": suitability.score, "coverage": suitability.coverage, "components": [asdict(c) for c in suitability.components]},
            "ranking": ranking_json(ranking), "placements": placement_json(placement_records), "fee": fee_json(fee),
            "strengths": strengths, "weaknesses": weaknesses,
            "data_gaps": data_gaps(placement_records, ranking, fee, quality.components),
            "why": [best["explanation"], best["quota_reason"]] + [c.note for c in suitability.components if c.score is not None and c.score >= 75],
        })

    # Seats without a band come last, since their one closing rank says little about next year.
    options.sort(key=lambda o: (o["band"] is None, -(o["suitability"]["score"] or 0), BAND_RANK.get(o["band"], 9), o["institution"]["short_name"], o["programme"], o["programme_id"]))
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
        "csab": csab_leads(db, profile, student, quota_map),
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
