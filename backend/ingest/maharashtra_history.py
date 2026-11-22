"""Several years of Maharashtra engineering (CAP) closing figures, for admission bands as on JEE.

Usage: python -m ingest.maharashtra_history
Reads data/raw/maharashtra-engineering/<year>/round<N>.pdf (see data/registry/exam_history.yaml) and adds a
`history` block to the maharashtra-engineering route in backend/snapshot/exam_routes.json. Run it after
ingest.exam_extract.

A seat is a course code, the section it was allotted under (State Level, Home University and so on) and a category.
Course codes are stable across years once padded to the current width, so no name matching is needed. A seat's
closing figure for a year is the worst state merit number it admitted in CAP rounds I to III, at any stage. Round
IV, held only in some years, is left out so every year is measured the same way.

Bands use the state merit number, not the percentile: in the backtest the Safer edge held for about 92% of seats
on merit numbers but only 58% to 70% on percentiles, which rose every year. Students give their merit number to
see bands; the percentile still places each seat by round, as before.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ingest.exam_extract import OUT, maharashtra_records
from ingest.neet_history import backtest_edges

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "maharashtra-engineering"
MAIN_ROUNDS = ("round1", "round2", "round3")


def section_of(group: str) -> str:
    return group.split(", Stage")[0]


def seat_key(programme_code: str, section: str, category: str) -> str:
    return f"{programme_code}|{section}|{category}"


def file_records(path: Path) -> list[dict]:
    """The reader's records for one file, cached next to it by the file's sha256."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    cache = path.with_name(f"{path.stem}.{digest}.records.json")
    if cache.exists():
        return json.loads(cache.read_text())
    records, check = maharashtra_records(path)
    if check["sequence_breaks"] > 0.001 * max(1, check["source_rows"]):
        raise SystemExit(f"{path}: {check}. Too many cells couldn't be read; check the file before loading.")
    cache.write_text(json.dumps(records))
    return records


def build() -> dict:
    years = sorted(int(p.name) for p in RAW.iterdir() if p.is_dir() and p.name.isdigit())
    closing: dict[str, dict[int, int]] = defaultdict(dict)
    check: dict[str, dict] = {}
    for year in years:
        for label in MAIN_ROUNDS:
            path = RAW / str(year) / f"{label}.pdf"
            if not path.exists():
                check[f"{year} {label}"] = {"missing": True}
                print(f"{year} {label}: missing", flush=True)
                continue
            try:
                records = file_records(path)
            except SystemExit as error:
                # A wrong document (such as an All India list) is reported and left out, never read as Maharashtra seats.
                check[f"{year} {label}"] = {"skipped": str(error)}
                print(f"{year} {label}: skipped. {error}", flush=True)
                continue
            seats = 0
            for record in records:
                if not record.get("second_value"):
                    continue
                key = seat_key(record["programme_code"], section_of(record["group"]), record["category"])
                closing[key][year] = max(closing[key].get(year, 0), record["second_value"])
                seats += 1
            check[f"{year} {label}"] = {"figures": seats}
            print(f"{year} {label}: {seats:,} closing figures", flush=True)
    complete = [y for y in years if all("figures" in check.get(f"{y} {label}", {}) for label in MAIN_ROUNDS)]
    tests = {
        str(y): backtest_edges(closing, y, lambda key: "State Level, GOPENS" if key.split("|")[1:] == ["State Level", "GOPENS"] else "Other seats")
        for y in complete if len([p for p in complete if y - 3 <= p < y]) >= 2
    }
    return {
        "years": years, "complete_years": complete, "uses": "second_value", "key": "programme_code|section|category",
        "basis": "Worst state merit number admitted in CAP rounds I to III of each year, per course, section and category.",
        "closing": {k: {str(y): v for y, v in sorted(by_year.items())} for k, by_year in sorted(closing.items())},
        "backtest": tests, "check": check,
    }


def main() -> None:
    data = json.loads(OUT.read_text())
    route = next(r for r in data["routes"] if r["code"] == "maharashtra-engineering")
    route["history"] = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    h = route["history"]
    print(f"{len(h['closing']):,} seats with history across {h['years'][0]}–{h['years'][-1]}")
    for year, groups in h["backtest"].items():
        for name, row in groups.items():
            print(f"  test {year} {name}: {row['seats']} seats, Safer edge held {row['safer']}%")
    if any("skipped" in c or "missing" in c for c in h["check"].values()):
        print("Some files were left out (see above). Years without all three rounds aren't used in the backtest.")


if __name__ == "__main__":
    main()
