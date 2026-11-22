"""KCET (KEA UGCET) engineering: the route from the latest year's cut-offs, with history for bands.

Usage: python -m ingest.kcet
Reads data/raw/kcet-engineering/<year>/round<N>-gen.pdf and -hk.pdf (see data/registry/exam_history.yaml) and
writes the `kcet-engineering` route, with a `history` block, into backend/snapshot/exam_routes.json.

KEA prints one table per college: a row per course and a column per category, each cell the cut-off rank of
that round (".5" ranks are KEA's own tie-breaks). From 2025 the courses are full names; in 2024 they are two-letter
codes with a short name. A seat is a college code, a course and a seat type (general or Kalyana Karnataka). 2024
joins the history only for codes that name one course without doubt (CODES_2024); other 2024 courses are left out
of the history rather than guessed. A seat's closing rank for a year is its worst cut-off over Rounds 1 and 2.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from ingest.exam_extract import OUT, clean, document
from ingest.neet_history import backtest_edges

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "kcet-engineering"
REGISTRY = ROOT / "data" / "registry" / "exam_history.yaml"
SEATS = {"gen": "General seats", "hk": "Kalyana Karnataka (371(J)) seats"}
ROUNDS = ("round1", "round2", "round3")
# History uses Rounds 1 and 2 only, so every year is measured the same way: the third list differs by year (an
# extended round in 2024) and isn't yet available for 2026.
HISTORY_ROUNDS = ("round1", "round2")
# 2024 two-letter course codes that name exactly one 2025-26 course, by that course's squashed name.
CODES_2024 = {
    "CS": "computerscienceandengineering", "EC": "electronicsandcommunicationengg", "ME": "mechanicalengineering",
    "CE": "civilengineering", "IE": "informationscienceandengineering", "EE": "electricalelectronicsengineering",
    "CA": "computerscienceandenggartificialintelligenceandmachinelearning",
    "DS": "computerscienceandengineeringdatascience", "AD": "artificialintelligenceanddatascience",
}
COLLEGE_NEW = re.compile(r"College:\s*(E\d{3})\s+(.*)")
COLLEGE_2024 = re.compile(r"^(E\d{3})\s+(.+)")


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def course_name(printed: str) -> str:
    """KEA prints courses in capitals and breaks words across lines ("DA TA"); show them in plain case."""
    name = clean(printed)
    name = re.sub(r"\b([A-Z]{1,3}) ([A-Z]{1,3})\b(?=\s*[A-Z)]|$)", lambda m: m.group(1) + m.group(2) if len(m.group(1) + m.group(2)) <= 4 and (m.group(1) + m.group(2)) in {"DATA", "ENGG"} else m.group(0), name)
    titled = name.title()
    for word in ("And", "Of", "In", "For", "The"):
        titled = re.sub(rf"\b{word}\b", word.lower(), titled)
    return re.sub(r"\bEngg\b", "Engg.", titled).replace("B Tech", "B.Tech").replace("Iot", "IoT").replace("Vlsi", "VLSI")


def read_file(path: Path) -> tuple[list[dict], dict]:
    """Every cut-off in one KEA file, with its college and course. Works for both the 2024 grid and the later tables."""
    records, check = [], Counter()
    college = None
    with pymupdf.open(path) as doc:
        for page in doc:
            items = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = clean("".join(span["text"] for span in line["spans"]))
                    match = COLLEGE_NEW.match(text) or COLLEGE_2024.match(text)
                    if match:
                        # Pages are often rotated; place the heading in the same frame as the tables.
                        top = (pymupdf.Rect(line["bbox"]) * page.rotation_matrix).y0
                        items.append((top, 0, (match.group(1), clean(match.group(2)))))
            for table in page.find_tables().tables:
                items.append((table.bbox[1], 1, table))
            # Each table belongs to the nearest college heading above it; a table at the top of a page continues the
            # last college from the page before.
            for _, kind, obj in sorted(items, key=lambda x: (x[0], x[1])):
                if kind == 0:
                    college = obj
                    continue
                data = obj.extract()
                header = [clean(c) for c in data[0]]
                layout_2024 = header[0] == ""
                if header[0] not in ("Course Name", ""):
                    check["other_tables"] += 1
                    continue
                if college is None:
                    check["no_college"] += 1
                    continue
                for row, raw in zip(obj.rows[1:], data[1:]):
                    first = clean(raw[0])
                    if not first and not any(clean(v) for v in raw[1:]):
                        continue
                    if layout_2024:
                        code, _, short = first.partition(" ")
                        course, key = clean(short), CODES_2024.get(code, f"2024:{code}")
                    else:
                        cell = row.cells[0]
                        printed = clean(page.get_text("text", clip=pymupdf.Rect(cell) * page.derotation_matrix)) if cell else first
                        course, key = course_name(printed), squash(printed)
                    for category, value in zip(header[1:], raw[1:]):
                        value = re.sub(r"\s+", "", value or "")
                        if not value or value == "--":
                            continue
                        records.append({"college_code": college[0], "college": college[1], "course": course, "course_key": key,
                                        "category": category, "rank": float(value)})
                        check["figures"] += 1
    check["colleges"] = len({r["college_code"] for r in records})
    return records, dict(check)


def file_records(path: Path) -> list[dict]:
    """The reader's records for one file, cached next to it by the file's sha256 (reading a file takes about a minute)."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    cache = path.with_name(f"{path.stem}.{digest}.records.json")
    if cache.exists():
        return json.loads(cache.read_text())
    records, check = read_file(path)
    if not records or check.get("no_college"):
        raise SystemExit(f"{path}: {check}. The layout wasn't recognised; check the file before loading.")
    cache.write_text(json.dumps(records))
    return records


# Words KEA sometimes prints only split across lines, so the joined form never appears whole to learn from.
SEED_WORDS = {"telecommunication", "intelligence", "artificial", "communication", "instrumentation", "engineering",
              "technology", "information", "electronics", "mechatronics", "manufacturing", "biotechnology"}


def rejoin_words(names: set[str]) -> dict[str, str]:
    """KEA breaks long words across lines inside a cell ("Telecommunica Tion"). Rejoin two neighbouring pieces when
    the joined word appears whole in another course name and at least one piece never appears on its own."""
    vocabulary = Counter(word.lower() for name in names for word in re.findall(r"[A-Za-z]+", name))
    known = set(vocabulary) | SEED_WORDS
    fixed = {}
    for name in names:
        spaced = re.sub(r"\s*\(\s*", " (", re.sub(r"\s*\)", ")", name)).strip()
        words, out = spaced.split(" "), []
        i = 0
        while i < len(words):
            if i + 1 < len(words):
                a, b = words[i], words[i + 1]
                joined = re.sub(r"[^A-Za-z]", "", a + b).lower()
                pieces = [re.sub(r"[^A-Za-z]", "", w).lower() for w in (a, b)]
                if joined in known and any(vocabulary[p] < 3 or len(p) <= 2 for p in pieces) and all(pieces):
                    out.append(a + b.lower())
                    i += 2
                    continue
            out.append(words[i])
            i += 1
        fixed[name] = re.sub(r"(\w)- (\w)", r"\1-\2", " ".join(out))
    return fixed


def short_name(college: str) -> str:
    return re.split(r",|\(", college)[0].strip()


def build() -> dict:
    import yaml

    registry = yaml.safe_load(REGISTRY.read_text())["routes"]["kcet-engineering"]["years"]
    years = sorted(int(p.name) for p in RAW.iterdir() if p.is_dir() and p.name.isdigit())
    latest = max(years)
    closing: dict[str, dict[int, int]] = defaultdict(dict)
    route_records, check, sources, rounds_latest = [], {}, [], []
    for year in years:
        for label in ROUNDS:
            for seat, seat_name in SEATS.items():
                name = f"{label}-{seat}"
                path = RAW / str(year) / f"{name}.pdf"
                if not path.exists():
                    check[f"{year} {name}"] = {"missing": True}
                    continue
                found = file_records(path)
                check[f"{year} {name}"] = {"figures": len(found)}
                title = registry[year][name]["title"]
                round_label = f"Round {label[-1]}" + (" (provisional)" if "provisional" in title else "")
                for r in found:
                    code = f"{r['college_code']}|{r['course_key']}|{seat}"
                    closing_key = f"{code}|{r['category']}"
                    if label in HISTORY_ROUNDS:
                        closing[closing_key][year] = max(closing[closing_key].get(year, 0), int(round(r["rank"])))
                    if year == latest:
                        route_records.append({
                            "institute": f"{r['college_code']} {r['college']}", "institute_short": short_name(r["college"]),
                            "programme": r["course"], "programme_code": code, "group": f"{seat_name} · {round_label}",
                            "category": r["category"], "value": int(round(r["rank"])),
                        })
                if year == latest:
                    sources.append({"title": title, "url": registry[year][name]["url"]})
                    if round_label not in rounds_latest:
                        rounds_latest.append(round_label)
    names = rejoin_words({r["programme"] for r in route_records})
    for record in route_records:
        record["programme"] = names[record["programme"]]
    complete = [y for y in years if all("figures" in check.get(f"{y} {r}-{s}", {}) for r in HISTORY_ROUNDS for s in SEATS)]
    tests = {
        str(y): backtest_edges(closing, y, lambda key: "General seats, GM" if key.endswith("|gen|GM") else "Other seats")
        for y in complete if len([p for p in complete if y - 3 <= p < y]) >= 2
    }
    missing = [k for k, v in check.items() if v.get("missing")]
    return {
        "code": "kcet-engineering", "stream": "Engineering", "level": "UG", "name": "KCET Engineering (Karnataka, KEA)", "authority": "Karnataka Examinations Authority",
        "compare_requires_group": True, "rounds": rounds_latest, "default_group": f"{SEATS['gen']} · {rounds_latest[0]}",
        "metric": {"label": "KCET rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "Cut-off rank", "second_label": None},
        "document": document(f"UGCET {latest} allotment cut-off ranks, engineering", sources[0]["url"], str(latest), ", ".join(rounds_latest), "official"),
        "sources": sources,
        "limits": [
            "Government (free and paid) seats KEA allots through UGCET, for candidates eligible under KEA's rules. COMEDK and management seats aren't included.",
            "Kalyana Karnataka (371(J)) seats are only for candidates with that region's eligibility certificate.",
            "Rounds marked provisional are from KEA's provisional cut-off lists, the only ones published for those rounds.",
            "Bands compare your rank with each seat's worst cut-off over Rounds 1 and 2 of recent years. For 2024, only the nine branches whose course code maps to one current course are matched.",
            *([f"Not available yet: {', '.join(missing)}."] if missing else []),
        ],
        "check": check, "records": route_records,
        "history": {
            "years": years, "complete_years": complete, "key": "programme_code|category",
            "basis": "Worst KEA cut-off rank over Rounds 1 and 2 of each year, per college, course, seat type and category.",
            "closing": {k: {str(y): v for y, v in sorted(by_year.items())} for k, by_year in sorted(closing.items())},
            "backtest": tests, "check": check,
        },
    }


def main() -> None:
    route = build()
    data = json.loads(OUT.read_text())
    data["routes"] = [r for r in data["routes"] if r["code"] != route["code"]] + [route]
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    h = route["history"]
    print(f"{len(route['records']):,} records for {h['years'][-1]}; {len(h['closing']):,} seats with history across {h['years'][0]}–{h['years'][-1]}")
    for name, c in route["check"].items():
        print(f"  {name}: {c}")
    for year, groups in h["backtest"].items():
        for name, row in groups.items():
            print(f"  test {year} {name}: {row['seats']} seats, Safer edge held {row['safer']}%")


if __name__ == "__main__":
    main()
