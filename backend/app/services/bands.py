"""Historical admission bands. Rule-based descriptions of past cutoffs, not probabilities.

No numerical chance is produced anywhere: outcomes for individual applicants are not
public, so a probability could not be calibrated. See docs/ADMISSION_ENGINE.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

Band = Literal["safer", "competitive", "ambitious", "beyond"]

LOOKBACK_YEARS = 3
MIN_YEARS_FOR_BAND = 2
SAFER_MARGIN = 0.90
AMBITIOUS_MARGIN = 1.20

BAND_RANK = {"safer": 0, "competitive": 1, "ambitious": 2, "beyond": 3}


@dataclass(frozen=True)
class CutoffPoint:
    year: int
    closing_rank: int


@dataclass(frozen=True)
class BandResult:
    band: Band | None
    low_closing: int | None
    high_closing: int | None
    latest_year: int | None
    latest_closing: int | None
    years_used: tuple[int, ...]
    explanation: str


def classify(rank: int, final_round_cutoffs: Sequence[CutoffPoint], latest_data_year: int) -> BandResult:
    """Place a rank against the same seat's final-round closing ranks from recent years.

    Lower rank numbers are better. A seat with too little recent history gets no band,
    which is reported as a data gap instead of being estimated.
    """
    window_start = latest_data_year - LOOKBACK_YEARS + 1
    recent = sorted((c for c in final_round_cutoffs if c.year >= window_start), key=lambda c: c.year)
    years = tuple(c.year for c in recent)
    if len(recent) < MIN_YEARS_FOR_BAND:
        latest = recent[-1] if recent else None
        # One closing rank can't place a seat in a band, but it can show a rank is far out of reach.
        if latest and rank > AMBITIOUS_MARGIN * latest.closing_rank:
            return BandResult(
                "beyond", None, None, latest.year, latest.closing_rank, years,
                f"Your rank {rank:,} is more than 20% beyond the only recent final-round closing rank ({latest.closing_rank:,} in {latest.year}).",
            )
        return BandResult(
            None, None, None, latest.year if latest else None, latest.closing_rank if latest else None, years,
            f"Only {len(recent)} year(s) of comparable history since {window_start}, so no band is shown.",
        )
    closings = [c.closing_rank for c in recent]
    low, high = min(closings), max(closings)
    span = f"{low:,} to {high:,} across {years[0]}–{years[-1]}"
    if rank <= SAFER_MARGIN * low:
        band: Band = "safer"
        text = f"Your rank {rank:,} is at least 10% inside every recent final-round closing rank ({span})."
    elif rank <= high:
        band = "competitive"
        text = f"Your rank {rank:,} is close to or within the recent closing range ({span})."
    elif rank <= AMBITIOUS_MARGIN * high:
        band = "ambitious"
        text = f"Your rank {rank:,} is outside the recent closing range ({span}), but within 20% of it."
    else:
        band = "beyond"
        text = f"Your rank {rank:,} is more than 20% beyond the recent closing range ({span})."
    return BandResult(band, low, high, recent[-1].year, recent[-1].closing_rank, years, text)
