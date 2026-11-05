"""Check a JoSAA preference list. It reports on the student's order and never changes it."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CutoffRecord, Programme, QuotaEligibleState
from app.schemas import StudentProfile
from app.services.bands import BAND_RANK, LOOKBACK_YEARS, CutoffPoint, classify
from app.services.branches import FAMILY_LABELS
from app.services.eligibility import exam_for, gender_pools, quota_applies, seat_claims
from app.services.recommend import PAPER_FOR_EXAM, latest_year

JOSAA_RULES = [
    "JoSAA allots you the highest choice on your list for which your rank qualifies in that round. Lower choices are then not considered.",
    "Your order should reflect what you want most, not what you think is most likely. A choice placed below one you are sure to get will usually never be reached.",
    "After an allotment you choose Freeze (keep it), Float (keep it, and upgrade to a higher choice if possible) or Slide (upgrade within the same institute). Check the current JoSAA rules, because they can change.",
    "This list is a planning aid and isn't submitted anywhere. You must enter your choices on the JoSAA portal yourself, and it applies its own rules.",
]


def analyse(db: Session, profile: StudentProfile, programme_ids: list[int]) -> dict:
    student = profile.to_student()
    data_year = latest_year(db)
    programmes = {p.id: p for p in db.scalars(select(Programme).where(Programme.id.in_(programme_ids)).options(joinedload(Programme.institution)))}
    records_by_programme: dict[int, list[CutoffRecord]] = {pid: [] for pid in programme_ids}
    for record in db.scalars(select(CutoffRecord).where(CutoffRecord.programme_id.in_(programme_ids), CutoffRecord.is_final_round, CutoffRecord.is_preparatory.is_(False), CutoffRecord.closing_rank.is_not(None), CutoffRecord.year > data_year - LOOKBACK_YEARS)):
        records_by_programme[record.programme_id].append(record)
    quota_map: dict[int, dict[str, set[str]]] = {}
    for row in db.scalars(select(QuotaEligibleState)):
        quota_map.setdefault(row.institution_id, {}).setdefault(row.quota, set()).add(row.state)

    items = []
    for position, programme_id in enumerate(programme_ids, start=1):
        programme = programmes.get(programme_id)
        if programme is None:
            items.append({"position": position, "programme_id": programme_id, "status": "unknown", "issues": ["This programme is no longer in the database."], "band": None})
            continue
        inst = programme.institution
        exam = exam_for(inst.institute_type)
        issues: list[str] = []
        claims = seat_claims(student, exam)
        if not claims:
            issues.append("IITs and IISc need a JEE Advanced rank." if exam == "JEE_ADVANCED" else "This needs a JEE Main rank, and none is on your profile.")
        if programme.required_paper != PAPER_FOR_EXAM[exam]:
            issues.append("This programme needs a different exam paper (B.Arch or B.Plan), which isn't checked here.")
        records = records_by_programme[programme_id]
        if records and max(r.year for r in records) < data_year or not records:
            issues.append(f"No {data_year} cutoff is on record, so check it is still offered.")
        routes = []
        for claim in claims:
            for pool in gender_pools(student):
                for quota in sorted({r.quota for r in records}):
                    applies, reason = quota_applies(quota, student.eligibility_state, inst.institute_type, quota_map.get(inst.id, {}))
                    if not applies:
                        continue
                    points = [CutoffPoint(r.year, r.closing_rank) for r in records if r.quota == quota and r.seat_type == claim.seat_type and r.gender_pool == pool and r.rank_list == claim.rank_list]
                    if points:
                        result = classify(claim.rank, points, data_year)
                        routes.append({"seat_type": claim.seat_type, "quota": quota, "gender_pool": pool, "band": result.band, "explanation": result.explanation, "rank_used": claim.rank, "rank_list": claim.rank_list})
        routes.sort(key=lambda r: (BAND_RANK.get(r["band"], 9), r["quota"], r["seat_type"], r["gender_pool"]))
        if claims and not routes and programme.required_paper == PAPER_FOR_EXAM[exam]:
            issues.append("No past cutoff matches your category, quota and seat pool for this programme.")
        items.append({
            "position": position, "programme_id": programme_id, "programme": programme.name, "degree": programme.degree,
            "branch_family": programme.branch_family, "branch_label": FAMILY_LABELS.get(programme.branch_family, "Other"),
            "institution": {"slug": inst.slug, "short_name": inst.short_name, "type": inst.institute_type, "state": inst.state},
            "status": "ok" if routes else "no_route", "band": routes[0]["band"] if routes else None, "routes": routes[:4], "issues": issues,
        })

    advice = []
    seen_safer = None
    for item in items:
        if seen_safer is not None and item["band"] in ("ambitious", "competitive", "beyond"):
            advice.append(f"Choice {item['position']} ({item.get('programme')} at {item['institution']['short_name']}) sits below choice {seen_safer}, which is in the safer range. If past cutoffs hold, it may never be reached. Move it up only if it's actually preferred.")
        if seen_safer is None and item["band"] == "safer":
            seen_safer = item["position"]
    usable = [i for i in items if i.get("band")]
    if usable and not any(i["band"] == "safer" for i in usable):
        advice.append("None of these choices are in the safer range, so past cutoffs suggest this list could end without a seat. Consider adding some options that would genuinely be acceptable.")
    if len(set(programme_ids)) != len(programme_ids):
        advice.append("The same programme appears more than once.")
    counts = {band: sum(1 for i in items if i.get("band") == band) for band in ("safer", "competitive", "ambitious", "beyond")}
    return {"items": items, "order_preserved": [i["programme_id"] for i in items] == programme_ids, "advice": advice, "counts": counts, "rules": JOSAA_RULES, "data_year": data_year}
