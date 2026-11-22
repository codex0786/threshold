"""Several years of Karnataka NEET UG (KEA state quota) closing ranks, for admission bands as on JEE.

Usage: python -m ingest.kea_history
Reads data/raw/karnataka-neet/<year>/<round>-<med|den>[-extra].pdf (see data/registry/exam_history.yaml) and adds
a `history` block to the karnataka-neet route in backend/snapshot/exam_routes.json. Run it after ingest.exam_extract.

A seat is KEA's course code (such as M001MG, which names the college and the seat type) and a category. KEA keeps
these codes from year to year, so no name matching is needed. A seat's closing rank for a year is the worst NEET
rank KEA allotted to it in rounds 1 to 3 (the third round was called the mop-up round before 2025).

KEA's pages are in Kannada and some links serve a different list than their label says, so every file's round is
read from its own title (each page's footer) and a file whose title names another round is left out.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

from ingest.exam_extract import OUT
from ingest.neet_history import backtest_edges

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "karnataka-neet"
MAIN_ROUNDS = ("round1", "round2", "round3")
ROUND_TITLE = {
    "round1": re.compile(r"\b1st ROUND\b", re.I),
    "round2": re.compile(r"\b2nd ROUND\b", re.I),
    "round3": re.compile(r"\b3rd ROUND\b|\bMOP[- ]*UP\b", re.I),
    "stray": re.compile(r"\bSTRAY\b", re.I),
}
OTHER_ROUND = re.compile(r"\bSTRAY\b|\bSPECIAL\b", re.I)


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def read_file(path: Path) -> dict:
    """The file's title and its allotments as (rank, course code, category), cached by the file's sha256."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    cache = path.with_name(f"{path.stem}.{digest}.allotments.json")
    if cache.exists():
        return json.loads(cache.read_text())
    rows, header = [], None
    with pymupdf.open(path) as doc:
        title = clean(doc[0].get_text() + " " + doc[-1].get_text())
        for page in doc:
            for table in page.find_tables().tables:
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if "SL.NO" in cells:
                        header = cells
                        continue
                    if header is None or not cells or not cells[0].isdigit():
                        continue
                    # The first column of each name counts: KEA's mop-up lists repeat the code for the previous round.
                    at = {name: cells[i] for i, name in reversed(list(enumerate(header))) if i < len(cells)}
                    rank = at.get("All India Rank") or at.get("Rank")
                    code = at.get("Course Code") or at.get("College Type")
                    category = at.get("Allotted Category")
                    if rank and rank.isdigit() and code and re.fullmatch(r"[MD]\d{3}[A-Z]{2}", code) and category:
                        rows.append([int(rank), code, category])
    found = {"title": title, "allotments": rows}
    cache.write_text(json.dumps(found))
    return found


def round_of(name: str) -> str:
    return name.split("-")[0]


def build() -> dict:
    years = sorted(int(p.name) for p in RAW.iterdir() if p.is_dir() and p.name.isdigit())
    closing: dict[str, dict[int, int]] = defaultdict(dict)
    check: dict[str, dict] = {}
    for year in years:
        for path in sorted((RAW / str(year)).glob("*.pdf")):
            label = path.stem
            found = read_file(path)
            wanted = ROUND_TITLE[round_of(label)]
            # A main-round file must name its own round and no stray or special round.
            if not wanted.search(found["title"]) or (round_of(label) != "stray" and OTHER_ROUND.search(found["title"])):
                check[f"{year} {label}"] = {"skipped": "its title names a different round"}
                print(f"{year} {label}: skipped, its title names a different round", flush=True)
                continue
            check[f"{year} {label}"] = {"allotted": len(found["allotments"])}
            print(f"{year} {label}: {len(found['allotments']):,} seats allotted", flush=True)
            if round_of(label) not in MAIN_ROUNDS:
                continue
            for rank, code, category in found["allotments"]:
                key = f"{code}|{category}"
                closing[key][year] = max(closing[key].get(year, 0), rank)

    def group_of(key: str) -> str:
        code, category = key.split("|")
        return "Government MBBS, GM" if code.startswith("M") and code.endswith("MG") and category == "GM" else "Other seats"

    tests = {str(y): backtest_edges(closing, y, group_of) for y in years if len([p for p in years if y - 3 <= p < y]) >= 2}
    return {
        "years": years, "key": "programme_code|category",
        "basis": "Worst NEET rank KEA allotted in rounds 1 to 3 of each year, per course code and category.",
        "closing": {k: {str(y): v for y, v in sorted(by_year.items())} for k, by_year in sorted(closing.items())},
        "backtest": tests, "check": check,
    }


def main() -> None:
    data = json.loads(OUT.read_text())
    route = next(r for r in data["routes"] if r["code"] == "karnataka-neet")
    route["history"] = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    h = route["history"]
    print(f"{len(h['closing']):,} seats with history across {h['years'][0]}–{h['years'][-1]}")
    for year, groups in h["backtest"].items():
        for name, row in groups.items():
            print(f"  test {year} {name}: {row['seats']} seats, Safer edge held {row['safer']}%")


if __name__ == "__main__":
    main()
