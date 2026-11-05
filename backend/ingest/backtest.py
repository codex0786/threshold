"""Check the band rules against the next year's published cutoffs.

For each seat, the three years before the test year set the band edges. We then ask
whether the test year's closing rank would still have admitted a rank at that edge.
This tests cutoff stability, not individual admission, and needs no applicant data.

Usage: python -m ingest.backtest --test-year 2026
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import select

from app.db import SessionLocal
from app.models import CutoffRecord, Institution, Programme
from app.services.bands import AMBITIOUS_MARGIN, LOOKBACK_YEARS, MIN_YEARS_FOR_BAND, SAFER_MARGIN


def run(test_year: int) -> dict:
    with SessionLocal() as db:
        rows = db.execute(
            select(CutoffRecord.programme_id, CutoffRecord.quota, CutoffRecord.seat_type, CutoffRecord.gender_pool, CutoffRecord.year, CutoffRecord.closing_rank, Institution.institute_type)
            .join(Programme, Programme.id == CutoffRecord.programme_id).join(Institution, Institution.id == Programme.institution_id)
            .where(
                CutoffRecord.is_final_round, CutoffRecord.is_preparatory.is_(False), CutoffRecord.closing_rank.is_not(None),
                CutoffRecord.year >= test_year - LOOKBACK_YEARS, CutoffRecord.year <= test_year,
            )
        ).all()
    seats: dict[tuple, dict] = defaultdict(lambda: {"history": [], "actual": None, "type": None})
    for programme_id, quota, seat_type, pool, year, closing, inst_type in rows:
        seat = seats[(programme_id, quota, seat_type, pool)]
        seat["type"] = inst_type
        if year == test_year:
            seat["actual"] = closing
        else:
            seat["history"].append(closing)
    groups: dict[str, dict] = defaultdict(lambda: {"seats": 0, "safer_edge_held": 0, "competitive_edge_held": 0, "ambitious_edge_held": 0})
    for key, seat in seats.items():
        if seat["actual"] is None or len(seat["history"]) < MIN_YEARS_FOR_BAND:
            continue
        low, high = min(seat["history"]), max(seat["history"])
        labels = ["all", "open_neutral" if key[2] == "OPEN" and key[3] == "neutral" else "other_seats"]
        for label in labels:
            group = groups[label]
            group["seats"] += 1
            group["safer_edge_held"] += SAFER_MARGIN * low <= seat["actual"]
            group["competitive_edge_held"] += high <= seat["actual"]
            group["ambitious_edge_held"] += AMBITIOUS_MARGIN * high <= seat["actual"]
    return dict(groups)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-year", type=int, default=2026)
    args = parser.parse_args()
    for label, g in sorted(run(args.test_year).items()):
        n = g["seats"]
        print(f"{args.test_year} {label}: seats={n:,} safer_edge={g['safer_edge_held'] / n:.1%} competitive_edge={g['competitive_edge_held'] / n:.1%} ambitious_edge={g['ambitious_edge_held'] / n:.1%}")


if __name__ == "__main__":
    main()
