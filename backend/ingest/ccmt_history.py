"""Several years of CCMT closing GATE scores, for admission bands on the GATE route.

Usage: python -m ingest.ccmt_history
Reads data/raw/ccmt/ccmt-<year>-orcr-from-page.json, one per year, each saved from CCMT's public score page
(linked from https://ccmt.admissions.nic.in/or-cr/). Rebuilds the gate-ccmt route from the latest year and adds a
`history` block to it in backend/snapshot/exam_routes.json. Run it after ingest.exam_extract; it keeps the NIRF
ranks and profiles that later steps attached, by institute.

A seat is an institute, a programme, a group and a category. Names are matched after removing case, spaces and
punctuation; the few institutes CCMT renamed between years are listed in RENAMED. A seat's closing score for a year
is the lowest minimum score it admitted in Rounds 1 to 3. The special and spot rounds are left out, because their
scores cover only newly allotted or upgraded candidates.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.services.bands import LOOKBACK_YEARS, MIN_YEARS_FOR_BAND, SCORE_MARGIN
from app.services.exam_routes import CCMT_RENAMED, ccmt_seat_key
from ingest.exam_extract import OUT, ccmt_route

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ccmt"
MAIN_ROUNDS = ("Round 1", "Round 2", "Round 3")
# Squashed names CCMT printed differently in some years, mapped to one name.
RENAMED = CCMT_RENAMED


def squash(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    return RENAMED.get(key, key)


def seat_key(institute: str, programme: str, group: str, category: str) -> str:
    """`group` is CCMT's own (G1, Group 1) or ours (Group 1 · Round 1); only its number is kept. Same key as the app's."""
    return ccmt_seat_key(institute, programme, group, category)


def year_files() -> dict[int, Path]:
    files = {}
    for path in sorted(RAW.glob("ccmt-*-orcr-from-page.json")):
        files[int(re.search(r"ccmt-(\d{4})-", path.name).group(1))] = path
    if not files:
        raise SystemExit(f"No CCMT files in {RAW}. Save each year's table from CCMT's score page first.")
    return files


def closing_scores(files: dict[int, Path]) -> tuple[dict[str, dict[int, int]], dict]:
    closing: dict[str, dict[int, int]] = defaultdict(dict)
    check = {}
    for year, path in files.items():
        saved = json.loads(path.read_text(encoding="utf-8"))
        rows = saved["rows"]
        if saved.get("total") not in (None, len(rows)):
            raise SystemExit(f"{path.name}: {len(rows)} rows saved but the page reported {saved['total']}")
        used = 0
        for round_label, institute, programme, group, category, _highest, lowest in rows:
            if round_label not in MAIN_ROUNDS:
                continue
            key = seat_key(institute, programme, group, category)
            closing[key][year] = min(closing[key].get(year, 1000), int(lowest))
            used += 1
        check[str(year)] = {"rows": len(rows), "main_round_rows": used}
    return closing, check


def backtest(closing: dict[str, dict[int, int]], test_year: int, margin: int = SCORE_MARGIN) -> dict:
    """Would a score exactly at each band edge, set by the years before, still have got the seat in `test_year`?

    Higher scores are better. A score at the Safer edge (the hardest recent year plus the margin) held if the
    seat's closing score that year was no higher.
    """
    groups: dict[str, Counter] = defaultdict(Counter)
    for key, by_year in closing.items():
        prior = [by_year[y] for y in range(test_year - LOOKBACK_YEARS, test_year) if y in by_year]
        if len(prior) < MIN_YEARS_FOR_BAND or test_year not in by_year:
            continue
        actual, low, high = by_year[test_year], min(prior), max(prior)
        _, _, group, category = key.split("|")
        for name in ("All seats", "Group 1, OPEN" if (group, category) == ("1", "OPEN") else "Other seats"):
            groups[name]["seats"] += 1
            groups[name]["safer"] += actual <= high + margin
            groups[name]["competitive"] += actual <= low
            groups[name]["ambitious"] += actual <= low - margin
    return {
        name: {"seats": c["seats"], **{edge: round(100 * c[edge] / c["seats"], 1) for edge in ("safer", "competitive", "ambitious")}}
        for name, c in sorted(groups.items())
    }


def build(files: dict[int, Path]) -> dict:
    closing, check = closing_scores(files)
    years = sorted(files)
    tests = {str(y): backtest(closing, y) for y in years if len([p for p in years if y - LOOKBACK_YEARS <= p < y]) >= MIN_YEARS_FOR_BAND}
    return {
        "years": years, "complete_years": years, "key": "institute|programme|group|category", "margin": SCORE_MARGIN,
        "basis": "Lowest GATE score admitted in CCMT Rounds 1 to 3 of each year, per institute, programme, group and category.",
        "closing": {k: {str(y): v for y, v in sorted(by_year.items())} for k, by_year in sorted(closing.items())},
        "backtest": tests, "check": check,
    }


def main() -> None:
    files = year_files()
    latest = max(files)
    data = json.loads(OUT.read_text())
    index = next(i for i, r in enumerate(data["routes"]) if r["code"] == "gate-ccmt")
    old = data["routes"][index]
    route = ccmt_route(files[latest])
    # NIRF ranks and other per-institute fields come from later steps; keep them for institutes that are still listed.
    extra = {squash(r["institute"]): {k: r[k] for k in ("ranking", "fee") if k in r} for r in old["records"]}
    for record in route["records"]:
        record.update(extra.get(squash(record["institute"]), {}))
    for field in ("profiles", "sources"):
        if field in old:
            route[field] = old[field]
    route["history"] = build(files)
    route["limits"].append(
        f"Bands compare your score with each seat's lowest admitted score in Rounds 1 to 3 of up to three recent years. "
        f"Safer means at least {SCORE_MARGIN} points above every one of them."
    )
    data["routes"][index] = route
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    h = route["history"]
    print(f"{len(route['records']):,} records for {latest}; {len(h['closing']):,} seats with history across {h['years'][0]}–{h['years'][-1]}")
    print(f"{len({squash(r['institute']) for r in route['records']} - set(extra))} institutes new in {latest} have no carried-over NIRF rank")
    for year, groups in h["backtest"].items():
        for name, row in groups.items():
            print(f"  test {year} {name}: {row['seats']} seats, Safer edge held {row['safer']}%")


if __name__ == "__main__":
    main()
