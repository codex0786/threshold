"""Faculty and academic indicators from NIRF submissions and an open research index.

Five things stay separate, because none stands in for another: teaching information, faculty
experience, faculty availability, research strength and academic resources. Nothing here rates a
teacher or a department. A ratio of people or a count of papers says nothing about how well anyone teaches.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AcademicSnapshot, AcademicYearRecord, ResearchOutput
from app.services.scoring import MIN_COHORT_INSTITUTIONS, percentile_of

# Averages from a handful of staff swing too much to compare.
MIN_REGULAR_FACULTY = 20
COMPARED_CATEGORY = "Engineering"
SCOPE_NOTE = "Covers the whole submission, not this department or branch. Self-reported to NIRF and not audited."
TEACHING_NOTE = "A count of people, which doesn't show how well anyone teaches."
RESEARCH_NOTE = "Research activity, which doesn't show teaching quality. Larger institutes also report larger totals."
OPENALEX_NOTE = "Papers and citations indexed by OpenAlex, matched on exact institute name. Coverage varies by field, and all departments are counted together."
SCORE_NOTE = "Compared only with other Engineering submissions, using per-person figures. Submissions may be a year apart."


def _per(value: float | None, people: int | None) -> float | None:
    return value / people if value is not None and people else None


def _mean(values: list) -> float | None:
    known = [v for v in values if v is not None]
    return mean(known) if known else None


def load(db: Session) -> dict[int, dict]:
    """Every institute's profile, with percentile scores for those in the comparable group."""
    snapshots = {s.institution_id: s for s in db.scalars(select(AcademicSnapshot).options(joinedload(AcademicSnapshot.source_document)))}
    years: dict[int, list[AcademicYearRecord]] = defaultdict(list)
    for row in db.scalars(select(AcademicYearRecord).order_by(AcademicYearRecord.academic_year.desc())):
        years[row.institution_id].append(row)
    outputs = {r.institution_id: r for r in db.scalars(select(ResearchOutput).options(joinedload(ResearchOutput.source)))}

    profiles: dict[int, dict] = {}
    for inst_id in set(snapshots) | set(outputs):
        profiles[inst_id] = _profile(snapshots.get(inst_id), years.get(inst_id, []), outputs.get(inst_id))
    _add_scores(profiles)
    return profiles


def _profile(snapshot: AcademicSnapshot | None, rows: list[AcademicYearRecord], output: ResearchOutput | None) -> dict:
    out: dict = {"scope_note": SCOPE_NOTE, "teaching": None, "experience": None, "availability": None, "research": None, "resources": None, "publications": None, "scores": {"faculty": None, "research": None}, "source": None}
    if output is not None:
        out["publications"] = {
            "works_count": output.works_count, "cited_by_count": output.cited_by_count, "h_index": output.h_index, "works_by_year": output.works_by_year,
            "note": OPENALEX_NOTE, "verification_status": output.verification_status, "source_url": output.external_id, "source_title": f"OpenAlex record: {output.matched_name}",
            "retrieved": output.retrieved_at.date().isoformat(),
        }
    if snapshot is None:
        return out
    regular = snapshot.faculty_regular or 0
    latest = rows[:3]
    out["source"] = {
        "title": snapshot.source_document.title, "url": snapshot.source_document.url, "submission_year": snapshot.submission_year, "category": snapshot.category,
        "verification_status": snapshot.verification_status, "issues": snapshot.problems,
    }
    out["teaching"] = {
        "students_total": snapshot.students_total, "faculty_regular": snapshot.faculty_regular,
        "students_per_regular_faculty": round(snapshot.students_total / regular, 1) if snapshot.students_total and regular else None, "note": TEACHING_NOTE,
    }
    out["experience"] = {
        "faculty_with_phd": snapshot.faculty_with_phd, "phd_share": round(snapshot.faculty_with_phd / regular, 3) if regular and snapshot.faculty_with_phd is not None else None,
        "median_experience_years": round(snapshot.median_experience_months / 12, 1) if snapshot.median_experience_months else None,
        "professors": snapshot.professors, "associate_professors": snapshot.associate_professors, "assistant_professors": snapshot.assistant_professors,
    }
    out["availability"] = {
        "faculty_listed": snapshot.faculty_listed, "faculty_current": snapshot.faculty_current, "faculty_regular": snapshot.faculty_regular,
        "faculty_other_current": (snapshot.faculty_current or 0) - regular if snapshot.faculty_current is not None else None,
        "note": "Regular faculty only are counted in ratios. Others currently working are visiting, adjunct or contractual.",
    }
    out["research"] = {
        "phd_students": snapshot.phd_students, "note": RESEARCH_NOTE,
        "years": [
            {"academic_year": r.academic_year, "phd_graduated": r.phd_graduated, "sponsored_projects": r.sponsored_projects, "sponsored_amount_inr": r.sponsored_amount_inr, "consultancy_amount_inr": r.consultancy_amount_inr, "patents_published": r.patents_published, "patents_granted": r.patents_granted}
            for r in latest
        ],
    }
    out["resources"] = {
        "note": "Spending on library resources and on new equipment for teaching and research, which doesn't show how good they are.",
        "years": [{"academic_year": r.academic_year, "library_spend_inr": r.library_spend_inr, "equipment_spend_inr": r.equipment_spend_inr} for r in latest],
    }
    out["_compare"] = {
        "eligible": snapshot.category == COMPARED_CATEGORY and regular >= MIN_REGULAR_FACULTY and not snapshot.problems,
        "ratio": out["teaching"]["students_per_regular_faculty"], "phd_share": out["experience"]["phd_share"],
        "funding": _per(_mean([r.sponsored_amount_inr for r in latest]), regular), "doctorates": _per(_mean([r.phd_graduated for r in latest]), regular),
    }
    return out


def _add_scores(profiles: dict[int, dict]) -> None:
    eligible = [p["_compare"] for p in profiles.values() if p.get("_compare", {}).get("eligible")]
    cohorts = {key: [c[key] for c in eligible if c[key] is not None] for key in ("ratio", "phd_share", "funding", "doctorates")}
    for profile in profiles.values():
        compare = profile.pop("_compare", None)
        if not compare or not compare["eligible"] or len(eligible) < MIN_COHORT_INSTITUTIONS:
            continue
        def at(key: str) -> float | None:
            return percentile_of(compare[key], cohorts[key]) if compare[key] is not None else None
        fewer_students = at("ratio")
        faculty = [100 - fewer_students if fewer_students is not None else None, at("phd_share")]
        research = [at("funding"), at("doctorates")]
        profile["scores"] = {
            "faculty": round(mean(faculty), 1) if None not in faculty else None,
            "research": round(mean(research), 1) if None not in research else None,
            "cohort_size": len(eligible), "note": SCORE_NOTE,
        }


def fit_inputs(profile: dict | None) -> dict:
    if not profile or not profile["scores"].get("faculty") and not profile["scores"].get("research"):
        return {}
    scores, inputs = profile["scores"], {}
    if scores["faculty"] is not None:
        teaching, experience = profile["teaching"], profile["experience"]
        inputs |= {"faculty_score": scores["faculty"], "faculty_note": f"{teaching['students_per_regular_faculty']} students per regular faculty member, and {round(experience['phd_share'] * 100)}% of regular faculty hold a doctorate. Whole institute, not this department"}
    if scores["research"] is not None:
        inputs |= {"research_score": scores["research"], "research_note": f"Funded research and doctorates per faculty member are above about {round(scores['research'])}% of {scores['cohort_size']} comparable institutes. This doesn't show teaching quality"}
    return inputs


def quality_evidence(profile: dict | None) -> tuple[float | None, str, float] | None:
    """Institute-wide, so it counts for half coverage, as institute-wide placements do."""
    if not profile:
        return None
    known = [s for s in (profile["scores"].get("faculty"), profile["scores"].get("research")) if s is not None]
    if not known:
        return None
    return round(mean(known), 1), "Faculty numbers, doctorates and funded research across the institute, not this department. Not a measure of teaching", 0.5


def summary(profile: dict | None) -> dict | None:
    """The short version for a shortlist card."""
    if not profile:
        return None
    return {
        "students_per_regular_faculty": (profile["teaching"] or {}).get("students_per_regular_faculty"), "phd_share": (profile["experience"] or {}).get("phd_share"),
        "faculty_regular": (profile["availability"] or {}).get("faculty_regular"), "scores": profile["scores"], "scope_note": profile["scope_note"],
        "source": profile["source"], "publications": profile["publications"],
    }
