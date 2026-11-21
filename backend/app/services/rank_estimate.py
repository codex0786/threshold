"""Estimate a JEE Main Common Rank List (CRL) rank from an NTA percentile.

A percentile says what share of a session's candidates scored at or below you. NTA builds the
final rank from each candidate's better session, over everyone who sat either session, so

    rank ~= (100 - percentile) / 100 x unique candidates

is close but not exact. We check it against the one point NTA publishes each year: the number
of candidates at or above the Unreserved cut-off for JEE Advanced. The observed ratio sets the
width of the range we show. Nothing here is a model of an individual result.

Figures are from NTA's press releases, read through the copies linked below.
Version the constants together and add each new year's row when NTA publishes it.
"""
from __future__ import annotations

from dataclasses import dataclass

ESTIMATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class YearFigures:
    year: int
    unique_appeared: int  # Paper 1, both sessions, unique candidates
    ur_cutoff_percentile: float  # lowest percentile in the UR (all) list for JEE Advanced
    ur_qualified: int  # candidates in that UR list
    source_url: str


YEARS: tuple[YearFigures, ...] = (
    YearFigures(2024, 1_415_110, 93.2362181, 97_351, "https://assets.collegedunia.com/public/image/JEE_Main_2024_Session_2_Toppers_List_327c17ee7179206ad1eb8e8d190c3407.pdf"),
    YearFigures(2025, 1_475_103, 93.1023262, 97_321, "https://www.collegedekho.com/news/jee-main-cut-off-2025-out-open-category-cutoff-at-931023262-percentile-category-wise-details-65180"),
    YearFigures(2026, 1_538_468, 93.4123549, 96_873, "https://collegedunia.com/news/how-many-students-appeared-for-jee-main-2026-alertid-150907"),
)


def naive_rank(percentile: float, candidates: int) -> float:
    return (100 - percentile) / 100 * candidates


def calibration_ratios() -> list[float]:
    """Published UR list size divided by what the plain formula predicts at that cut-off."""
    return [y.ur_qualified / naive_rank(y.ur_cutoff_percentile, y.unique_appeared) for y in YEARS]


def growth_rates() -> list[float]:
    ordered = sorted(YEARS, key=lambda y: y.year)
    return [b.unique_appeared / a.unique_appeared for a, b in zip(ordered, ordered[1:])]


def estimate(percentile: float, exam_year: int) -> dict:
    """A rank range for a percentile. Never a single number, and never below rank 1."""
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    latest = max(YEARS, key=lambda y: y.year)
    known = {y.year: y for y in YEARS}
    if exam_year in known:
        low_n = high_n = known[exam_year].unique_appeared
        candidates_note = f"{known[exam_year].unique_appeared:,} candidates sat JEE Main {exam_year}, as NTA reported."
    else:
        years_ahead = max(1, exam_year - latest.year)
        growth = growth_rates()
        low_n = latest.unique_appeared * min(1.0, min(growth)) ** years_ahead
        high_n = latest.unique_appeared * max(growth) ** years_ahead
        candidates_note = (
            f"NTA hasn't published the {exam_year} count yet. We assume between {round(low_n):,} and {round(high_n):,} candidates: "
            f"no fewer than {latest.year}'s {latest.unique_appeared:,}, and growth no faster than the last few years."
        )
    ratios = calibration_ratios()
    low = max(1, round(naive_rank(percentile, low_n) * min(ratios)))
    high = max(1, round(naive_rank(percentile, high_n) * max(ratios)))
    warnings = []
    if percentile < 80:
        warnings.append("We could only check the method near the 93rd percentile. Below about 80, treat the range as rougher.")
    if percentile >= 99.99:
        warnings.append("At the very top, a few candidates share each percentile, so ranks can differ by more than this range suggests.")
    return {
        "percentile": percentile, "exam_year": exam_year, "rank_low": low, "rank_high": high,
        "rank_list": "JEE_MAIN:CRL", "candidates_note": candidates_note,
        "method": [
            "Rank is about (100 minus your percentile) out of every 100 candidates who sat the exam.",
            f"We checked this against NTA's published JEE Advanced qualifier counts for {', '.join(str(y.year) for y in YEARS)}. "
            f"The real count was {min(ratios):.2f} to {max(ratios):.2f} times the simple formula, and the range covers that spread.",
            "If you sat both sessions, use your higher percentile. NTA ranks you on your better session.",
            "This estimates your Common Rank List (CRL) rank only. Category ranks depend on how many candidates of each category scored above you, which NTA doesn't publish in a usable form.",
        ],
        "warnings": warnings,
        "sources": [{"year": y.year, "url": y.source_url} for y in YEARS],
        "version": ESTIMATOR_VERSION,
    }
