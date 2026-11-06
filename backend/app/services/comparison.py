"""Side-by-side comparison with rule-based trade-offs. It never declares a single winner."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CutoffRecord, Programme, QuotaEligibleState
from app.schemas import StudentProfile
from app.services import careers
from app.services import recommend as rec
from app.services.bands import BAND_RANK, LOOKBACK_YEARS, CutoffPoint, classify
from app.services.branches import FAMILY_LABELS
from app.services.eligibility import exam_for, gender_pools, quota_applies, seat_claims
from app.services.scoring import FitInputs, quality_score, suitability_score

BROAD_CAREER_NOTES = {
    "CS": "typically leads to software and data roles, and to some non-technical roles",
    "AI_DS": "focuses on data and machine learning roles, usually with a newer curriculum and fewer past graduates",
    "MATH_COMP": "combines mathematics with computing, and can suit software, data, quantitative and research paths",
    "ECE": "can lead to hardware, semiconductor and communications work as well as software",
    "EE": "can lead to power, electronics and control work, and also to software",
    "ME": "leads to manufacturing, design and energy work, and is a common route into core engineering",
    "CIVIL": "leads to infrastructure, construction and public-sector engineering work",
    "CHEM_E": "leads to process, energy and materials industries",
    "AERO": "leads to aerospace and defence work, a smaller and more specialised job market",
    "MATERIALS": "leads to metals, materials and mining industries",
    "BIO": "leads to biotechnology, food and healthcare industries, where further study is often useful",
    "SCIENCE": "builds a science foundation, which often suits research and further study",
    "ROBOTICS": "combines mechanical, electronic and software skills",
    "OCEAN": "leads to shipping and offshore industries, a smaller and more specialised job market",
}


def _reference_cutoff(records: list[CutoffRecord]) -> dict | None:
    """Pick a comparable reference: OPEN, gender-neutral, final round, preferring OS or AI over HS."""
    candidates = [r for r in records if r.seat_type == "OPEN" and r.gender_pool == "neutral" and r.is_final_round and r.closing_rank and not r.is_preparatory]
    if not candidates:
        return None
    order = {"AI": 0, "OS": 1, "HS": 2}
    latest = max(r.year for r in candidates)
    pick = min((r for r in candidates if r.year == latest), key=lambda r: order.get(r.quota, 9))
    return {"year": pick.year, "quota": pick.quota, "closing_rank": pick.closing_rank, "rank_list": pick.rank_list, "source_url": pick.source_document.url, "source_title": pick.source_document.title}


def _student_route(profile: StudentProfile, programme: Programme, records: list[CutoffRecord], quota_states: dict[str, set[str]], data_year: int) -> dict | None:
    student = profile.to_student()
    inst = programme.institution
    claims = seat_claims(student, exam_for(inst.institute_type))
    results = []
    for claim in claims:
        for pool in gender_pools(student):
            for quota in {r.quota for r in records}:
                applies, reason = quota_applies(quota, student.eligibility_state, inst.institute_type, quota_states)
                if not applies:
                    continue
                points = [
                    CutoffPoint(r.year, r.closing_rank) for r in records
                    if r.is_final_round and r.quota == quota and r.seat_type == claim.seat_type and r.gender_pool == pool
                    and r.rank_list == claim.rank_list and r.closing_rank and not r.is_preparatory
                    and r.year > data_year - LOOKBACK_YEARS
                ]
                if not points:
                    continue
                band = classify(claim.rank, points, data_year)
                results.append({"band": band.band, "explanation": band.explanation, "quota": quota, "seat_type": claim.seat_type, "gender_pool": pool, "rank_used": claim.rank, "rank_list": claim.rank_list, "quota_reason": reason})
    if not results:
        return None
    return min(results, key=lambda r: (BAND_RANK.get(r["band"], 9), r["quota"], r["seat_type"], r["gender_pool"]))


def _trade_offs(items: list[dict]) -> list[str]:
    notes: list[str] = []
    ranked = [i for i in items if i["ranking"]]
    unranked = [i for i in items if not i["ranking"]]
    if len(ranked) >= 2:
        ordered = sorted(ranked, key=lambda i: i["ranking"]["rank"])
        by_institute = {i["institution"]["short_name"]: i["ranking"]["rank"] for i in ordered}
        text = ", ".join(f"{name} ({rank})" for name, rank in by_institute.items())
        notes.append(f"NIRF {ordered[0]['ranking']['year']} Engineering ranks: {text}. This ranks whole institutes, not individual branches.")
    if ranked and unranked:
        names = ", ".join(dict.fromkeys(i["institution"]["short_name"] for i in unranked))
        notes.append(f"{names}: no NIRF rank is on record here. That is a gap in our data, not evidence of lower quality.")
    families = {i["branch_family"] for i in items}
    if len(families) > 1:
        for item in items:
            career_note = BROAD_CAREER_NOTES.get(item["branch_family"])
            if career_note:
                notes.append(f"{item['programme']} at {item['institution']['short_name']} {career_note}. This is a general description, not institute data.")
    else:
        notes.append("All options share a branch family, so the main differences are institute and location.")
    institutes = {i["institution"]["slug"] for i in items}
    prestige_vs_branch = len(ranked) >= 2 and len(families) > 1 and len(institutes) > 1
    if prestige_vs_branch:
        notes.append("A higher-ranked institute with a branch you do not want and a lower-ranked institute with a branch you do want are different bets. Check each institute's branch-change rules, because they vary and are not guaranteed.")
    nirf = {}
    for item in items:
        latest = next((p for p in item["placements"] if p["reporting_definition"] == "nirf_graduation_outcomes" and p["median_salary_inr"]), None)
        if latest:
            nirf[item["institution"]["short_name"]] = latest
    if len(nirf) >= 2:
        text = ", ".join(f"{name} Rs {record['median_salary_inr'] / 100000:.2f} lakh ({record['graduation_year']})" for name, record in nirf.items())
        notes.append(f"Institute-wide median salary reported to NIRF: {text}. These cover all 4-year students at each institute, not these branches.")
    branch = {}
    for item in items:
        own = next((p for p in item["placements"] if p["scope"] == "programme" and p["median_salary_inr"]), None)
        if own:
            branch[f"{item['programme']} at {item['institution']['short_name']}"] = own
    if branch:
        text = ", ".join(f"{name} Rs {record['median_salary_inr'] / 100000:.2f} lakh CTC ({record['graduation_year']})" for name, record in branch.items())
        notes.append(f"Branch-level median from the institute's own report: {text}. CTC isn't the same as take-home pay, and each institute defines its report differently, so compare across institutes with care.")
    without_branch = [i for i in items if not any(p["scope"] == "programme" for p in i["placements"])]
    if branch and without_branch:
        names = ", ".join(dict.fromkeys(i["institution"]["short_name"] for i in without_branch))
        notes.append(f"No branch-level figures are on record for {names}.")
    missing = [i for i in items if not i["placements"]]
    if len(missing) == len(items):
        notes.append("No verified placement data is available for any of these options, so career outcomes cannot be compared yet.")
    elif missing:
        names = ", ".join(dict.fromkeys(i["institution"]["short_name"] for i in missing))
        notes.append(f"Placement data is missing for {names}, so outcomes cannot be compared across all the options.")
    return notes


def compare(db: Session, programme_ids: list[int], profile: StudentProfile | None) -> dict | None:
    programmes = {
        p.id: p for p in db.scalars(select(Programme).where(Programme.id.in_(programme_ids)).options(joinedload(Programme.institution)))
    }
    if len(programmes) != len(programme_ids):
        return None
    evidence = rec.institution_evidence(db)
    data_year = rec.latest_year(db)
    goals = rec.career_goal_families(profile.career_goals) if profile else None
    contest = rec.contest_view(db, data_year) if profile else {}
    lineage = rec.lineage_map(db)
    items = []
    for programme_id in programme_ids:
        programme = programmes[programme_id]
        inst = programme.institution
        records = db.scalars(select(CutoffRecord).options(joinedload(CutoffRecord.source_document)).where(CutoffRecord.programme_id.in_(rec.history_ids(lineage, programme_id)))).all()
        quota_states: dict[str, set[str]] = {}
        for row in db.scalars(select(QuotaEligibleState).where(QuotaEligibleState.institution_id == inst.id)):
            quota_states.setdefault(row.quota, set()).add(row.state)
        ranking = rec.ranking_for(programme, evidence)
        fee = rec.fee_for(programme, evidence)
        placement_records, career = rec.career_for(programme, evidence)
        note = f"NIRF {ranking.year} rank {ranking.rank} ({ranking.verification_status.replace('_', ' ')})" if ranking else ""
        quality = quality_score(ranking.rank if ranking else None, note, career)
        item = {
            "programme_id": programme.id, "programme": programme.name, "degree": programme.degree, "duration_years": programme.duration_years,
            "branch_family": programme.branch_family, "branch_label": FAMILY_LABELS.get(programme.branch_family, "Other"),
            "institution": rec.institution_json(programme, full=False),
            "reference_cutoff": _reference_cutoff(list(records)), "ranking": rec.ranking_json(ranking),
            "placements": rec.placement_json(placement_records), "fee": rec.fee_json(fee), "quality": rec.describe_quality(quality),
            "data_gaps": rec.data_gaps(placement_records, ranking, fee, quality.components),
            "faculty": None, "curriculum": None, "careers": careers.career_profile(db, inst.id), "student_experience": None,
            "student_route": None, "suitability": None,
        }
        if profile:
            item["student_route"] = _student_route(profile, programme, list(records), quota_states, data_year)
            fit = suitability_score(FitInputs(
                branch_family=programme.branch_family, institute_type=inst.institute_type, state=rec.location_of(programme)[1],
                nirf_rank=ranking.rank if ranking else None, career_dimension_score=career[0], **rec.cost_inputs(fee, profile),
                preferred_branches=frozenset(profile.preferred_branches), acceptable_branches=frozenset(profile.acceptable_branches),
                career_goal_families=goals, preferred_states=frozenset(profile.preferred_states), preferred_types=frozenset(profile.preferred_types),
                annual_budget_inr=profile.annual_budget_inr, career_note=career[1], priorities=profile.priorities,
                **rec.fit_contest(contest, programme_id),
            ))
            item["suitability"] = {"score": fit.score, "coverage": fit.coverage, "components": [c.__dict__ for c in fit.components]}
        items.append(item)
    return {"items": items, "trade_offs": _trade_offs(items), "note": "Reference cutoffs use OPEN, gender-neutral seats from the final round. Ranks from JEE Main and JEE Advanced are on different lists and are not directly comparable."}
