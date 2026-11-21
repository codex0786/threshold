"""Several years of NEET UG (MCC All India counselling) closing ranks, for admission bands as on JEE.

Usage: python -m ingest.neet_history
Reads data/raw/neet-ug/<year>/{round1,round2,round3,stray}.pdf (see data/registry/exam_history.yaml) and adds a
`history` block to the neet-ug route in backend/snapshot/exam_routes.json. Run it after ingest.exam_extract.

What a "closing rank" means here: the worst NEET rank allotted to a seat (institute, course, quota, category) in
rounds 1 to 3 of a year. The stray round is left out: it only fills seats still empty at the end, under its own
eligibility, and including it made the bands less reliable in the backtest (see docs/ADMISSION_ENGINE.md).

MCC prints institute names differently across rounds and years (with or without the address, and reworded in
2026), so names are linked by the words and PIN code that identify a college, never by generic words such as
"Government Medical College". A link is made only between spellings that never appear in the same year.

Reading the tables is slow (about 0.1 s a page, 25,000 pages), so each file's rows are cached next to it as
<label>.<sha256 prefix>.rows.jsonl, which is git-ignored with the rest of data/raw.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from app.services.bands import AMBITIOUS_MARGIN, LOOKBACK_YEARS, MIN_YEARS_FOR_BAND, SAFER_MARGIN
from ingest.exam_extract import NEET_CATEGORIES, NEET_COURSES, OUT, institute_name

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "neet-ug"
ROUNDS = ("round1", "round2", "round3", "stray")
MAIN_ROUNDS = ("round1", "round2", "round3")
GENERIC = set("""govt government govermant goverment medical college colleges hospital hospitals and the institute institution sciences
 science research centre center dental university medicine health ltd trust society road near post dist district state city nagar new old
 bypass campus main mch hosp inst sci med coll education educational national memorial general rural com ail gmail yahoo rediffmail
 nic org edu""".split())
REGIONS = set("""andhra pradesh arunachal assam bihar chhattisgarh goa gujarat haryana himachal jharkhand karnataka kerala madhya maharashtra
 manipur meghalaya mizoram nagaland odisha orissa punjab rajasthan sikkim tamil nadu telangana tripura uttar uttarakhand west bengal delhi
 jammu kashmir puducherry pondicherry india""".split())
LINK_THRESHOLD = 0.5


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def table_rows(path: Path) -> list[list[str | None]]:
    # Named by the file's sha256, so a changed or re-downloaded file never reuses old rows.
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    cache = path.with_name(f"{path.stem}.{digest}.rows.jsonl")
    if cache.exists():
        return [json.loads(line) for line in cache.read_text().splitlines() if line]
    rows = []
    with pymupdf.open(path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                rows.extend(table.extract())
    cache.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return rows


def _number(cell: str | None) -> int | None:
    # Wide numbers wrap inside narrow columns ("1000\n0"), and tied ranks carry a suffix ("1(A)").
    match = re.match(r"\d+", re.sub(r"\s+", "", cell or ""))
    return int(match.group()) if match else None


def allotments(rows: list[list[str | None]]) -> tuple[list[tuple], Counter]:
    """(rank, quota, institute, course, category) for every seat allotted in one round's file.

    Round 1 and stray files have eight columns (serial, rank, quota, institute, course, allotted category,
    candidate category, remarks). Round 2 and 3 files carry each candidate's earlier rounds too, four columns a
    round, then this round's seven; some years leave out the serial column, which the width shows.
    """
    found, check = [], Counter()
    for raw in rows:
        cells = [re.sub(r"\s+", " ", c or "").strip() for c in raw]
        width = len(cells)
        if not re.fullmatch(r"\d+", re.sub(r"\s+", "", raw[0] or "")):
            continue
        if width == 8:
            rank, (quota, institute, course, category) = _number(raw[1]), cells[2:6]
        elif width >= 12 and (width - 8) % 4 in (0, 1):
            rank = _number(raw[1]) if (width - 8) % 4 == 1 else _number(raw[0])
            quota, institute, course, category = cells[-7:-3]
        else:
            check["unknown_layout"] += 1
            continue
        check["rows"] += 1
        if quota in ("-", ""):
            check["no_seat_this_round"] += 1
            continue
        if rank is None or course not in NEET_COURSES or category not in NEET_CATEGORIES:
            check["unreadable"] += 1
            continue
        # The full printed name, contact email included: without it several colleges print as just
        # "Government Medical College", which would merge them.
        found.append((rank, quota, institute, course, category))
    return found, check


def _tokens(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 2 and w not in GENERIC and w not in REGIONS}


def _pins(name: str) -> set[str]:
    return set(re.findall(r"(?<!\d)(\d{6})(?!\d)", re.sub(r"\s", "", name)))


def link_institutes(seen: dict[str, dict]) -> dict[str, str]:
    """One id per institute, from every spelling. `seen` maps a spelling to its years and courses."""
    # A spelling that starts with a shorter one is the same name with its address added.
    spelled = {squash(name): name for name in seen}
    ordered = sorted(spelled, key=len)
    # A short name made only of generic words ("Government Medical College") says nothing about which college it is.
    distinctive = {c for c in ordered if len(c) >= 12 and _tokens(spelled[c])}
    prefix: dict[str, str] = {}
    for name in ordered:
        shorter = next((c for c in ordered if c in distinctive and len(c) < len(name) and name.startswith(c)), None)
        prefix[name] = prefix.get(shorter, shorter) if shorter else name
    info: dict[str, dict] = defaultdict(lambda: {"names": set(), "years": set(), "courses": set()})
    for name, data in seen.items():
        entry = info[prefix[squash(name)]]
        entry["names"].add(name)
        entry["years"] |= data["years"]
        entry["courses"] |= data["courses"]
    for entry in info.values():
        entry["tokens"] = set().union(*(_tokens(n) for n in entry["names"]))
        entry["pins"] = set().union(*(_pins(n) for n in entry["names"]))

    def score(a: dict, b: dict) -> float:
        if not a["courses"] & b["courses"]:
            return 0.0
        overlap = len(a["tokens"] & b["tokens"]) / max(1, len(a["tokens"] | b["tokens"]))
        if a["pins"] and b["pins"]:
            overlap += 0.5 if a["pins"] & b["pins"] else -0.5
        return overlap

    keys = sorted(info)
    pairs = sorted(
        ((score(info[a], info[b]), a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if not info[a]["years"] & info[b]["years"]),
        reverse=True,
    )
    parent = {k: k for k in keys}
    years = {k: set(info[k]["years"]) for k in keys}

    def root(k: str) -> str:
        while parent[k] != k:
            k = parent[k]
        return k

    for value, a, b in pairs:
        if value < LINK_THRESHOLD:
            break
        ra, rb = root(a), root(b)
        if ra != rb and not years[ra] & years[rb]:
            parent[rb] = ra
            years[ra] |= years.pop(rb)
    # The id is the newest spelling, so it reads like the name students see now.
    newest: dict[str, tuple] = {}
    for k in keys:
        r = root(k)
        candidate = (max(info[k]["years"]), -len(k), k)
        newest[r] = max(newest.get(r, candidate), candidate)
    return {name: newest[root(prefix[squash(name)])][2] for name in seen}


def shown_names(ids: dict[str, str]) -> dict[str, str]:
    """Institute id by the name the route's records show (contact email removed), only where that name is unambiguous."""
    found: dict[str, set[str]] = defaultdict(set)
    for name, institute_id in ids.items():
        found[squash(institute_name(name))].add(institute_id)
    return {name: next(iter(id_set)) for name, id_set in sorted(found.items()) if len(id_set) == 1 and name}


def seat_key(institute_id: str, course: str, quota: str, category: str) -> str:
    return f"{institute_id}|{course}|{squash(quota)}|{category}"


def backtest(closing: dict[str, dict[int, int]], test_year: int) -> dict:
    """Would a rank exactly at each band edge, set by the years before, still have got the seat in `test_year`?"""
    groups: dict[str, Counter] = defaultdict(Counter)
    for key, by_year in closing.items():
        prior = [by_year[y] for y in range(test_year - LOOKBACK_YEARS, test_year) if y in by_year]
        if len(prior) < MIN_YEARS_FOR_BAND or test_year not in by_year:
            continue
        actual, low, high = by_year[test_year], min(prior), max(prior)
        _, course, quota, category = key.split("|")
        group = "All India quota, Open, MBBS" if (course, quota, category) == ("MBBS", "allindia", "Open") else "Other seats"
        for name in ("All seats", group):
            groups[name]["seats"] += 1
            groups[name]["safer"] += SAFER_MARGIN * low <= actual
            groups[name]["competitive"] += high <= actual
            groups[name]["ambitious"] += AMBITIOUS_MARGIN * high <= actual
    return {
        name: {"seats": c["seats"], **{edge: round(100 * c[edge] / c["seats"], 1) for edge in ("safer", "competitive", "ambitious")}}
        for name, c in sorted(groups.items())
    }


def build() -> dict:
    years = sorted(int(p.name) for p in RAW.iterdir() if p.is_dir() and p.name.isdigit())
    per_round: dict[tuple[int, str], list[tuple]] = {}
    checks: dict[str, dict] = {}
    for year in years:
        for label in ROUNDS:
            path = RAW / str(year) / f"{label}.pdf"
            if not path.exists():
                raise SystemExit(f"Missing {path}. Run python -m ingest.fetch_exam_history first.")
            found, check = allotments(table_rows(path))
            if check["unreadable"] or check["unknown_layout"]:
                raise SystemExit(f"{year} {label}: {dict(check)}. The file's layout has changed; check it before loading.")
            per_round[(year, label)] = found
            checks[f"{year} {label}"] = {"allotted": len(found), **check}
            print(f"{year} {label}: {len(found):,} seats allotted", flush=True)
    seen: dict[str, dict] = defaultdict(lambda: {"years": set(), "courses": set()})
    for (year, _), found in per_round.items():
        for _, _, institute, course, _ in found:
            seen[institute]["years"].add(year)
            seen[institute]["courses"].add(course)
    ids = link_institutes(seen)
    closing: dict[str, dict[int, int]] = defaultdict(dict)
    for (year, label), found in per_round.items():
        if label not in MAIN_ROUNDS:
            continue
        for rank, quota, institute, course, category in found:
            key = seat_key(ids[institute], course, quota, category)
            closing[key][year] = max(closing[key].get(year, 0), rank)
    tests = {str(y): backtest(closing, y) for y in years if y - LOOKBACK_YEARS >= years[0] - 1 and y > years[0] + 1}
    return {
        "years": years, "basis": "Worst rank allotted in rounds 1 to 3 of each year, per institute, course, quota and category.",
        "institutes": shown_names(ids), "institute_count": len(set(ids.values())),
        "closing": {k: {str(y): v for y, v in sorted(by_year.items())} for k, by_year in sorted(closing.items())},
        "backtest": tests, "check": checks,
    }


def main() -> None:
    data = json.loads(OUT.read_text())
    route = next(r for r in data["routes"] if r["code"] == "neet-ug")
    route["history"] = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    h = route["history"]
    print(f"{h['institute_count']} institutes, {len(h['closing']):,} seats with history across {h['years'][0]}–{h['years'][-1]}")
    for year, groups in h["backtest"].items():
        for name, row in groups.items():
            print(f"  test {year} {name}: {row['seats']} seats, Safer edge held {row['safer']}%")


if __name__ == "__main__":
    main()
