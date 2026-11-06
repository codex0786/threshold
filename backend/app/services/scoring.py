"""Quality and suitability scoring. Pure, deterministic and explainable.

Quality describes the option. Suitability describes the fit with one student. Admission
bands live in bands.py. The three are never merged into one number.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from statistics import median
from typing import Mapping, Sequence

ENGINE_VERSION = "0.5.0"
MIN_QUALITY_COVERAGE = 0.5
# Salary percentiles among a few selected institutes would mislead, so wait for a broad cohort.
MIN_COHORT_INSTITUTIONS = 50
# A median from a very small graduating class is too noisy to rank against other institutes.
MIN_GRADUATING_CLASS = 100
NEUTRAL = 50.0

# Initial product assumptions, not validated universal weights.
QUALITY_WEIGHTS: dict[str, float] = {
    "career_outcomes": 25, "academic_faculty": 18, "branch_curriculum": 15, "alumni_network": 12,
    "institutional_reputation": 10, "financial_return": 10, "student_experience": 5, "location_opportunities": 5,
}
QUALITY_LABELS = {
    "career_outcomes": "Career and placement outcomes", "academic_faculty": "Academic and faculty quality",
    "branch_curriculum": "Branch strength and curriculum", "alumni_network": "Alumni and industry network",
    "institutional_reputation": "Institutional reputation", "financial_return": "Financial return",
    "student_experience": "Student experience", "location_opportunities": "Location and opportunities",
}
DEFAULT_PRIORITIES: dict[str, float] = {
    "branch_fit": 30, "career_fit": 20, "reputation": 20, "location": 10, "institution_type": 5,
    "placements": 10, "affordability": 5, "demand": 20,
    # Off unless a student turns them on. Figures exist for about half of institutes, so a default weight would favour those that publish.
    "faculty": 0, "research": 0,
}
SUITABILITY_LABELS = {
    "branch_fit": "Branch preference", "career_fit": "Career goal", "reputation": "Institutional reputation",
    "location": "Location", "institution_type": "Institution type", "placements": "Placement outcomes",
    "affordability": "Affordability", "demand": "How contested the seat is",
    "faculty": "Faculty numbers and qualifications", "research": "Funded research and doctoral output",
}


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    weight: float
    score: float | None
    note: str


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    coverage: float
    components: tuple[Component, ...]
    status: str = "scored"


@dataclass(frozen=True)
class PlacementEvidence:
    scope: str  # programme | institution
    median_salary_inr: int | None
    eligible: int | None
    placed: int | None
    year: int
    reporting_definition: str = "institute_placement_report"
    graduating: int | None = None


def reputation_score(nirf_rank: int | None) -> float | None:
    """Rank 1 maps to 100 and rank 100 to 50.5. No rank means no evidence, and counts as a neutral 50.

    Being on the list never scores below being absent from it. NIRF ranks only institutes that take
    part, so absence doesn't show that an institute would rank lower.
    """
    if nirf_rank is None:
        return None
    return max(50.5, 100.0 - (nirf_rank - 1) * 0.5)


def standing_score(nirf_rank: int | None, demand: float | None, preferred: bool = False, acceptable: bool = False) -> float:
    """Default list position: two parts institute rank to one part how contested the programme is.

    Only orders the list. It isn't a quality score and never affects a band. A missing rank or closing
    rank counts as neutral, as elsewhere. A branch the student asked for moves up without hiding the rest.
    """
    institute = reputation_score(nirf_rank)
    institute = NEUTRAL if institute is None else institute
    contested = NEUTRAL if demand is None else demand
    return round((2 * institute + contested) / 3 + (10 if preferred else 5 if acceptable else 0), 1)


def contest_scores(closing_ranks: Mapping[int, float]) -> dict[int, float]:
    """Share of comparable programmes that close at a weaker rank, on a 0-100 scale. Lower closing ranks are more contested."""
    values = sorted(closing_ranks.values())
    return {key: round(100.0 * (len(values) - bisect_right(values, rank)) / len(values), 1) for key, rank in closing_ranks.items()}


def percentile_of(value: float, cohort: Sequence[float]) -> float | None:
    """Share of a like-for-like cohort at or below the value, on a 0-100 scale."""
    if len(cohort) < 2:
        return None
    return round(100.0 * sum(1 for x in cohort if x <= value) / len(cohort), 1)


def career_score(
    records: Sequence[PlacementEvidence], cohorts_by_year: Mapping[int, Sequence[float]], min_cohort: int = MIN_COHORT_INSTITUTIONS,
) -> tuple[float | None, str, float]:
    """Score placements using medians and rates, never the highest package.

    A salary is only compared with others from the same graduating year and reporting
    definition. Years with fewer than min_cohort institutes are not used. Returns
    (score, note, evidence_factor). Institute-wide data counts for half coverage, because
    it says nothing specific about a branch.
    """
    programme = [r for r in records if r.scope == "programme"]
    usable = programme or [r for r in records if r.scope == "institution"]
    if not usable:
        return None, "Data not available", 0.0
    factor = 1.0 if programme else 0.5
    scope_text = "programme-level" if programme else "institute-wide, not branch-specific"
    percentiles: dict[int, float] = {}
    small = [r for r in usable if r.graduating is not None and r.graduating < MIN_GRADUATING_CLASS]
    for record in usable:
        cohort = cohorts_by_year.get(record.year, ())
        if record in small:
            continue
        if record.median_salary_inr and len(cohort) >= min_cohort:
            percentile = percentile_of(record.median_salary_inr, cohort)
            if percentile is not None:
                percentiles[record.year] = percentile
    rates = [100.0 * r.placed / r.eligible for r in usable if r.placed is not None and r.eligible]
    if not percentiles and small:
        return None, f"Figures are shown ({scope_text}) but not scored: fewer than {MIN_GRADUATING_CLASS} students graduated, so the median is too uncertain to rank", 0.0
    if not percentiles:
        largest = max((len(cohorts_by_year.get(r.year, ())) for r in usable), default=0)
        return None, (
            f"Figures are shown ({scope_text}) but not scored: at most {largest} comparable institutes "
            f"share a graduating year with this one, and at least {min_cohort} are needed for a fair comparison"
        ), 0.0
    average = sum(percentiles.values()) / len(percentiles)
    parts = [average]
    if rates:
        parts.append(min(100.0, median(rates)))
    years = sorted(percentiles)
    size = min(len(cohorts_by_year[year]) for year in years)
    span = f"{years[0]}" if len(years) == 1 else f"{years[0]}–{years[-1]}"
    return round(sum(parts) / len(parts), 1), f"Self-reported median salary at or above about {round(average)}% of {size}+ comparable institutes, graduating {span} ({scope_text})", factor


def quality_score(nirf_rank: int | None, nirf_note: str, career: tuple[float | None, str, float], academic: tuple[float | None, str, float] | None = None) -> ScoreResult:
    """Combine available evidence using the published weights. Below minimum coverage, no score is given."""
    values: dict[str, tuple[float | None, str, float]] = {
        key: (None, "Data not available", 0.0) for key in QUALITY_WEIGHTS
    }
    values["career_outcomes"] = career
    if academic is not None:
        values["academic_faculty"] = academic
    rep = reputation_score(nirf_rank)
    values["institutional_reputation"] = (rep, nirf_note if rep is not None else "Not in the recorded NIRF list", 1.0 if rep is not None else 0.0)
    total_weight = sum(QUALITY_WEIGHTS.values())
    covered = sum(QUALITY_WEIGHTS[k] * v[2] for k, v in values.items() if v[0] is not None)
    coverage = covered / total_weight
    components = tuple(
        Component(k, QUALITY_LABELS[k], QUALITY_WEIGHTS[k], values[k][0], values[k][1]) for k in QUALITY_WEIGHTS
    )
    if coverage < MIN_QUALITY_COVERAGE:
        return ScoreResult(None, round(coverage, 3), components, "insufficient_evidence")
    weighted = sum(QUALITY_WEIGHTS[k] * v[2] * v[0] for k, v in values.items() if v[0] is not None)
    return ScoreResult(round(weighted / covered, 1), round(coverage, 3), components)


@dataclass(frozen=True)
class FitInputs:
    branch_family: str
    institute_type: str
    state: str
    nirf_rank: int | None
    career_dimension_score: float | None
    annual_cost_inr: int | None
    preferred_branches: frozenset[str] = frozenset()
    acceptable_branches: frozenset[str] = frozenset()
    career_goal_families: frozenset[str] | None = None
    preferred_states: frozenset[str] = frozenset()
    preferred_types: frozenset[str] = frozenset()
    annual_budget_inr: int | None = None
    career_note: str = "Data not available"
    demand_score: float | None = None
    demand_note: str = "No all-comers cutoff to compare"
    # Charges on record when the yearly cost is incomplete. It can show a budget is exceeded, never that it is met.
    annual_known_inr: int | None = None
    cost_note: str | None = None
    faculty_score: float | None = None
    research_score: float | None = None
    faculty_note: str = "No faculty figures on record"
    research_note: str = "No research figures on record"
    priorities: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRIORITIES))


def suitability_score(f: FitInputs) -> ScoreResult:
    """Weighted fit from 0 to 100. Unknown dimensions count as neutral, so gaps neither help nor hurt."""
    dims: dict[str, tuple[float | None, str]] = {}
    if f.preferred_branches or f.acceptable_branches:
        if f.branch_family in f.preferred_branches:
            dims["branch_fit"] = (100.0, "A preferred branch")
        elif f.branch_family in f.acceptable_branches:
            dims["branch_fit"] = (60.0, "An acceptable branch")
        else:
            dims["branch_fit"] = (25.0, "Not on your branch lists")
    else:
        dims["branch_fit"] = (None, "No branch preference given")
    if f.career_goal_families is None:
        dims["career_fit"] = (None, "No career goal mapped to a branch (assumption table)")
    elif f.branch_family in f.career_goal_families:
        dims["career_fit"] = (100.0, "Branch commonly leads towards your goal (product assumption)")
    else:
        dims["career_fit"] = (30.0, "Branch is a less direct route to your goal (product assumption)")
    rep = reputation_score(f.nirf_rank)
    dims["reputation"] = (rep, f"NIRF Engineering rank {f.nirf_rank}" if rep is not None else "No NIRF rank on record")
    if f.preferred_states:
        match = f.state in f.preferred_states
        dims["location"] = (100.0 if match else 30.0, f"In {f.state}, " + ("a preferred state" if match else "not a preferred state"))
    else:
        dims["location"] = (None, "No location preference given")
    if f.preferred_types:
        match = f.institute_type in f.preferred_types
        dims["institution_type"] = (100.0 if match else 30.0, f"{f.institute_type} is " + ("a preferred type" if match else "not a preferred type"))
    else:
        dims["institution_type"] = (None, "No institution type preference given")
    dims["placements"] = (f.career_dimension_score, f.career_note)
    if f.annual_cost_inr is not None and f.annual_budget_inr:
        ratio = f.annual_cost_inr / f.annual_budget_inr
        dims["affordability"] = (max(0.0, min(100.0, 100.0 * (2 - ratio))), "Compared with your annual budget")
    elif not f.annual_budget_inr:
        dims["affordability"] = (None, "No budget given")
    elif f.annual_known_inr is not None and f.annual_known_inr > f.annual_budget_inr:
        ratio = f.annual_known_inr / f.annual_budget_inr
        dims["affordability"] = (max(0.0, 100.0 * (2 - ratio)), "Recorded charges alone are above your annual budget, before any hostel or mess costs missing from the record")
    elif f.annual_known_inr is not None:
        dims["affordability"] = (None, "Recorded charges are within your budget, but hostel or mess costs are missing, so this isn't scored")
    else:
        dims["affordability"] = (None, f.cost_note or "No yearly cost on record")
    dims["demand"] = (f.demand_score, f.demand_note)
    dims["faculty"] = (f.faculty_score, f.faculty_note)
    dims["research"] = (f.research_score, f.research_note)

    total = sum(max(0.0, f.priorities.get(k, 0.0)) for k in dims)
    if total <= 0:
        return ScoreResult(None, 0.0, (), "no_priorities")
    points = 0.0
    known = 0.0
    components = []
    for key, (score, note) in dims.items():
        weight = max(0.0, f.priorities.get(key, 0.0))
        points += weight * (score if score is not None else NEUTRAL)
        known += weight if score is not None else 0.0
        components.append(Component(key, SUITABILITY_LABELS[key], round(100 * weight / total, 1), score, note))
    return ScoreResult(round(points / total, 1), round(known / total, 3), tuple(components))
