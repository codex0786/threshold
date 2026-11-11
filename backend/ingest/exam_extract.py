"""Extract official documents for the admission routes beyond JEE.

Writes the git-ignored backend/snapshot/exam_routes.json. This repository is public, so don't commit it.
Candidate-level identifiers (such as CLAT admit card numbers) are never read
into the output.

Usage: python -m ingest.exam_extract --mcc-stray a.pdf --mcc-round2 b.pdf --mcc-round3 c.pdf [--mcc-round1 r1.pdf] --clat d/*.pdf \
           [--maharashtra round-I.pdf round-II.pdf ...] [--ccmt f.json] [--kea data/raw/kea]
Routes whose inputs aren't given are kept from the existing file, so a slow source needn't be re-read.
Then run `python -m ingest.mcc_fees` and `python -m ingest.exam_rankings`, in that order.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parents[1] / "snapshot" / "exam_routes.json"
RETRIEVED = "2026-11-08"
CLAT_RESERVATION_END = "Note :"


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


NEET_COURSES = {"MBBS", "BDS", "B.Sc. Nursing"}
NEET_CATEGORIES = {"Open", "OBC", "SC", "ST", "EWS", "Open PwD", "OBC PwD", "SC PwD", "ST PwD", "EWS PwD"}


def institute_name(text: str | None) -> str:
    # Some institute names in the source end with a contact email, which isn't part of the name.
    return re.sub(r",?\s*\S+@\S+", "", clean(text))


def quota_name(text: str | None) -> str:
    return re.sub(r"-\s+", "-", clean(text))


def mcc_quota_key(path: Path) -> list[str]:
    """Quota names as MCC's own key on page 1 prints them, each on one line."""
    with pymupdf.open(path) as doc:
        lines = [clean(line) for line in doc[0].get_text().splitlines() if clean(line)]
    start = lines.index("Description") + 1
    return [line for line in lines[start:] if not re.fullmatch(r"[A-Z]{2}( PwD)?", line)]


def spellings(names: list[str], known: list[str] = ()) -> dict[str, str]:
    """Map every spelling of a name to one. Names wrap across lines in the larger files, which adds stray spaces
    ("Children/Wid ows", "AIIMS, New Delhi , ANSARI"). Spellings that match without spaces are the same name.
    A spelling from MCC's own key wins, and otherwise the one with the fewest spaces."""
    def key(name: str) -> str:
        return re.sub(r"\s+", "", name).lower()

    best: dict[str, str] = {key(name): name for name in known}
    for name in names:
        current = best.get(key(name))
        if current is None or (current not in known and name.count(" ") < current.count(" ")):
            best[key(name)] = name
    return {name: best[key(name)] for name in names}


def tidy_quotas(records: list[dict], known: list[str] = ()) -> list[dict]:
    """Give each quota and institute one spelling, then merge records the variants had split."""
    quotas = spellings([r["group"].rsplit(" · ", 1)[0] for r in records], known)
    institutes = spellings([r["institute"] for r in records])
    merged: dict[tuple, dict] = {}
    for record in records:
        quota, round_label = record["group"].rsplit(" · ", 1)
        record = {**record, "group": f"{quotas[quota]} · {round_label}", "institute": institutes[record["institute"]]}
        identity = (record["institute"], record["programme"], record["group"], record["category"])
        if identity in merged:
            seen = merged[identity]
            seen["value"], seen["first_value"], seen["count"] = max(seen["value"], record["value"]), min(seen["first_value"], record["first_value"]), seen["count"] + record["count"]
        else:
            merged[identity] = record
    return list(merged.values())


# CLAT headings spell the same course several ways, and two run the course into the university name.
CLAT_COURSE = re.compile(r"[\s-]*\b(B\.?\s?(?:A|B\.?\s?A|Com|Sc)\.?,?\s?LL\.?\s?B.*)$")
CLAT_COURSES = [("B.Sc", "BSc LLB (Hons)"), ("BSc", "BSc LLB (Hons)"), ("B.Com", "BCom LLB (Hons)"), ("B.B.A", "BBA LLB (Hons)"), ("B.A", "BA LLB (Hons)")]


def clat_heading(heading: str) -> tuple[str, str]:
    """Split a CLAT heading into university and course, naming each course one way."""
    match = CLAT_COURSE.search(heading)
    if not match:
        return heading, "5-Year Integrated Law (UG)"
    course = match.group(1)
    name = next(label for prefix, label in CLAT_COURSES if course.replace(" ", "").startswith(prefix.replace(" ", "")))
    detail = re.search(r"\[(.+?)\]", course)
    return heading[:match.start()].strip(" -"), f"{name}, {detail.group(1)}" if detail else name


# MCC marks seats only women may hold by adding "(Female Seat only)" to the institute name.
FEMALE_ONLY = re.compile(r"female\s*seat\s*only", re.I)


def last_ranks(groups: dict[tuple, list[int]], round_label: str) -> list[dict]:
    """The last rank allotted per seat. Each record is our calculation, not an MCC figure."""
    return [
        {
            "institute": k[0], "programme": k[1], "group": f"{k[2]} · {round_label}", "category": k[3], "value": max(v), "first_value": min(v), "count": len(v),
            "female_only": bool(FEMALE_ONLY.search(k[0])),
        }
        for k, v in groups.items()
    ]


def mcc_round_records(path: Path, round_label: str) -> tuple[list[dict], dict]:
    """Seats allotted in one main round, from MCC's rank-wise table.

    Each row is one candidate. The last seven cells are this round's allotment, the only round whose allotted
    category the file gives. A "-" there means no seat in this round, for example a candidate who kept an
    earlier seat, so that row is skipped.
    """
    groups: dict[tuple, list[int]] = defaultdict(list)
    rows = skipped = bad = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                for row in table.extract():
                    cells = [clean(c) for c in row]
                    if not cells or not re.fullmatch(r"\d+", cells[0]):
                        continue
                    rows += 1
                    # The layout leaves an empty spacer column in some rows.
                    cells = [c for i, c in enumerate(cells) if c or i < 5]
                    quota, institute, course, allotted, _candidate, _option, _remark = cells[-7:]
                    if quota in ("-", ""):
                        skipped += 1
                        continue
                    if course not in NEET_COURSES or allotted not in NEET_CATEGORIES:
                        bad += 1
                        continue
                    groups[(institute_name(institute), course, quota_name(quota), allotted)].append(int(cells[0]))
    return last_ranks(groups, round_label), {"source_rows": rows, "no_seat_this_round": skipped, "sequence_breaks": bad}


def mcc_records(path: Path, round_label: str = "Stray round") -> tuple[list[dict], dict]:
    """Allotments in MCC's narrower layout, used for Round 1 and the stray round."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    rows = breaks = last = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                for row in table.extract():
                    serial = clean(row[0])
                    if not re.fullmatch(r"\d+", serial) or len(row) != 8:
                        continue
                    rank = clean(row[1])
                    if int(serial) != last + 1 or not re.fullmatch(r"\d+", rank):
                        breaks += 1
                    last = int(serial)
                    rows += 1
                    groups[(institute_name(row[3]), clean(row[4]), quota_name(row[2]), clean(row[5]))].append(int(rank))
    return last_ranks(groups, round_label), {"source_rows": rows, "sequence_breaks": breaks}


def clat_records(path: Path) -> tuple[list[dict], dict]:
    """Read only the Cut-Off Rank Table. Rows holding admit card numbers are never parsed."""
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    institute, programme = clat_heading(clean(re.search(r"Provisional 5th List.*?\n(.+?)\n", text).group(1)))
    block = text[text.index("Cut-Off Rank Table"):]
    block = block[:block.index(CLAT_RESERVATION_END)]
    records = []
    section, label = "Vertical", []
    for line in [clean(l) for l in block.splitlines()][5:]:
        if line in ("Vertical Reservation", "Horizontals Reservation"):
            section = line.split()[0].rstrip("s")
        elif line:
            label.append(line)
        words = [x for x in label if not re.fullmatch(r"\d+|\*\*", x)]
        values = [x for x in label if re.fullmatch(r"\d+|\*\*", x)]
        if len(values) == 3:
            seats, air, category_rank = values
            records.append({
                "institute": institute, "programme": programme, "group": f"{section} reservation",
                "category": " ".join(words), "seats": None if seats == "**" else int(seats),
                "value": None if air == "**" else int(air), "second_value": None if category_rank == "**" else int(category_rank),
                "note": "Deemed fulfilled, so no cut-off is given" if air == "**" else None,
            })
            label = []
    return records, {"source_rows": len(records), "sequence_breaks": 0}


MH_CELL = re.compile(r"^(\d+)\s*\((\d+(?:\.\d+)?)\)$")
MH_SECTION = re.compile(r"^(State Level|(Home University|Other Than Home University|Minority|Maharashtra State) Seats Allotted to .+)$")
# Stages as the CET Cell prints them. Later rounds add stages such as VII, I-Non PWD, I-Non Defence and MH (minority seats).
MH_STAGE = re.compile(r"^(?:(?:I|II|III|IV|V|VI|VII|VIII|IX|X)(?:-Non (?:PWD|Defence))?|MH)$")
MH_ROUND_ORDER = ["I", "II", "III", "IV", "V"]
# The CET Cell's public document pages for each round's Maharashtra and minority cut-off list, 2025-26.
MH_SOURCES = [
    {"title": f"Cut Off List for Maharashtra & Minority Seats, CAP Round {r}, 2025-26", "url": f"https://fe2025.mahacet.org/ViewPublicDocument.aspx?MenuId={menu}"}
    for r, menu in (("I", 2449), ("II", 3475), ("III", 3483), ("IV", 9822))
]
MH_TITLE = re.compile(r"CAP Round\s*-?\s*([IVX]+)\b.*?(?:A\.Y\.|for the Year)\s*(\d{4}-\d{2})", re.S)


def page_lines(page: pymupdf.Page) -> list[tuple[float, str]]:
    lines = [(line["bbox"][1], clean("".join(span["text"] for span in line["spans"]))) for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])]
    return sorted(line for line in lines if line[1])


def maharashtra_records(path: Path) -> tuple[list[dict], dict]:
    """Closing merit number and percentile for every published stage, under the seat codes as published.

    A course code starts with its institute's code, so the institute comes from the code, not page position.
    """
    records: list[dict] = []
    bad = unknown_institute = inferred_later_stage = spilled = 0
    programme = programme_code = section = None
    in_programme_name = False

    def read_heading(line: str) -> None:
        nonlocal programme, programme_code, section, in_programme_name
        if match := re.match(r"^(\d{10}[A-Z]*) - (.+)$", line):
            programme_code, programme = match.groups()
            section, in_programme_name = None, True
        elif line.startswith("Status"):
            in_programme_name = False
        elif re.match(r"^\d{5} - ", line):
            return
        elif in_programme_name:
            programme = f"{programme} {line}"
        elif MH_SECTION.match(line):
            section = line

    # Wide tables spill onto a page with no headings, at the same height as the table they continue.
    parents: list[tuple[float, str, str, str]] = []
    with pymupdf.open(path) as doc:
        institutes = {code: clean(name) for page in doc for code, name in re.findall(r"(?m)^(\d{5}) - (.+)$", page.get_text())}
        for page in doc:
            lines = page_lines(page)
            overflow = not any(line == "State Common Entrance Test Cell" for _, line in lines)
            if not overflow:
                parents = []
            position = 0
            for table in sorted(page.find_tables().tables, key=lambda t: t.bbox[1]):
                if overflow:
                    parent = next((p for p in parents if abs(p[0] - table.bbox[1]) < 3), None)
                    if parent is None:
                        bad += 1
                        continue
                    _, table_code, table_programme, table_section = parent
                else:
                    while position < len(lines) and lines[position][0] < table.bbox[1]:
                        read_heading(lines[position][1])
                        position += 1
                    position = next((i for i, line in enumerate(lines) if line[0] >= table.bbox[3]), len(lines))
                    table_code, table_programme, table_section = programme_code, programme, section
                    parents.append((table.bbox[1], table_code, table_programme, table_section))
                rows = table.extract()
                codes = [clean(c).replace(" ", "") for c in rows[0]]
                # The detector sometimes leaves the Stage column out of the table, so the row order gives the stage.
                has_stage_column = codes[0] in ("", "Stage")
                if not has_stage_column and len(rows) > 2:
                    inferred_later_stage += len(rows) - 2
                for index, row in enumerate(rows[1:], start=1):
                    stage = clean(row[0]) if has_stage_column else "I" * index
                    cells = zip(codes[1:], row[1:]) if has_stage_column else zip(codes, row)
                    for code, cell in cells:
                        cell = clean(cell)
                        if not cell:
                            continue
                        match = MH_CELL.match(cell)
                        if not match or not MH_STAGE.match(stage) or not table_section or not code:
                            bad += 1
                            continue
                        institute = institutes.get(table_code[:5])
                        if institute is None:
                            unknown_institute += 1
                            continue
                        percentile = float(match.group(2))
                        records.append({
                            "institute": institute, "programme": table_programme, "programme_code": table_code,
                            "group": f"{table_section}, Stage {stage}", "category": code,
                            # The source prints 0.0000000 beside some merit numbers, which can't be a real closing percentile.
                            "value": percentile or None, "second_value": int(match.group(1)),
                            "note": None if percentile else "The source shows a percentile of 0 here, so only its merit number is shown",
                        })
            if not overflow:
                for _, line in lines[position:]:
                    read_heading(line)
                continue
            # A single spilled column has no grid, so the table finder misses it and only its text remains.
            boxes = [t.bbox for t in page.find_tables().tables]
            loose = [(y, line) for y, line in lines if not any(b[1] <= y <= b[3] for b in boxes)]
            for (y, code), (_, merit), (_, percentile) in zip(loose[::3], loose[1::3], loose[2::3]):
                parent = next((p for p in parents if 0 <= y - p[0] < 15), None)
                match = MH_CELL.match(f"{merit} {percentile}")
                if parent is None or not match:
                    bad += 1
                    continue
                spilled += 1
                records.append({
                    "institute": institutes[parent[1][:5]], "programme": parent[2], "programme_code": parent[1],
                    "group": f"{parent[3]}, Stage I", "category": code,
                    "value": float(match.group(2)) or None, "second_value": int(match.group(1)), "note": None,
                })
        title = MH_TITLE.search(doc[0].get_text())
    if title is None:
        raise SystemExit(f"No CAP round in the title of {path}")
    round_label = f"CAP Round {title.group(1)}, {title.group(2)}"
    for record in records:
        record["group"] = f"{record['group']} · {round_label}"
    return records, {
        "round": round_label, "source_rows": len(records), "sequence_breaks": bad, "unknown_institute": unknown_institute,
        "inferred_later_stage": inferred_later_stage, "spilled_columns": spilled,
    }


def clat_all(paths: list[Path]) -> tuple[list[dict], dict]:
    records: list[dict] = []
    for path in sorted(paths):
        found, _ = clat_records(path)
        records += found
    return records, {"source_rows": len(records), "files": len(paths), "sequence_breaks": 0}


def short_names(names: list[str]) -> dict[str, str]:
    """MCC prints an institute as its name then its address, joined by a comma with no space after it.
    The name is the part before that comma, or the first two parts where the name alone isn't unique."""
    def cut(name: str, parts: int) -> str:
        pieces = re.split(r",(?=\S)", name)
        return re.sub(r"\s*\(Female Seat only\s*\)", "", ",".join(pieces[:parts])).strip(" ,")

    first = {name: cut(name, 1) for name in names}
    counts: dict[str, int] = defaultdict(int)
    for short in first.values():
        counts[short] += 1
    return {name: short if counts[short] == 1 else cut(name, 2) for name, short in first.items()}


# Quotas only some candidates may use, named by what they require. Every other quota is open to all.
# From MCC's quota key on page 1 of each allotment file. MCC's information bulletin has the full rules.
NEET_QUOTA_REQUIREMENTS = {
    "Non-Resident Indian": "NRI", "Non-Resident Indian(AMU) Quota": "NRI",
    "Employees State Insurance Scheme(ESI)": "Ward of an ESI insured person",
    "Employees State Insurance Scheme Nursing Quota (ESI-IP Quota Nursing)": "Ward of an ESI insured person",
    "Muslim Minority Quota": "Muslim minority", "Muslim OBC Quota": "Muslim minority", "Muslim ST Quota": "Muslim minority",
    "Muslim Women Quota": "Muslim minority", "Muslim Quota": "Muslim minority", "Jain Minority Quota": "Jain minority",
    "Aligarh Muslim University (AMU) Quota": "AMU internal", "(AMU)Self finance internal": "AMU internal",
    "Jamia Internal Quota": "Jamia internal", "Internal -Puducherry UT Domicile": "Puducherry domicile",
    "Delhi University Quota": "Delhi University quota (Delhi NCR)", "IP University Quota": "IP University quota (Delhi NCR)",
    "B.Sc Nursing Delhi NCR": "Delhi NCR domicile",
    "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) DU Quota": "Child or widow of armed forces personnel (CW)",
    "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) IP Quota": "Child or widow of armed forces personnel (CW)",
    "B.Sc Nursing Delhi NCR CW Quota": "Child or widow of armed forces personnel (CW)",
    "B.Sc Nursing IP CW Quota": "Child or widow of armed forces personnel (CW)",
}

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Jammu and Kashmir", "Delhi",
    "Dadra and Nagar Haveli and Daman and Diu", "Puducherry", "Chandigarh", "Ladakh",
]
STATE_SPELLINGS = {"Tamilnadu": "Tamil Nadu", "Uttarpradesh": "Uttar Pradesh", "J & K Residents": "Jammu and Kashmir", "of MH": "Maharashtra"}
# State codes as they end the Consortium's category codes, for example (DV-KL) or (CDFP-MP-SC).
STATE_CODES = {
    "AP": "Andhra Pradesh", "AS": "Assam", "BH": "Bihar", "BR": "Bihar", "CHT": "Chhattisgarh", "DDN": "Dadra and Nagar Haveli and Daman and Diu",
    "GA": "Goa", "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana", "JD": "Jharkhand", "KA": "Karnataka", "KL": "Kerala",
    "MH": "Maharashtra", "MP": "Madhya Pradesh", "OD": "Odisha", "PB": "Punjab", "RJ": "Rajasthan", "TL": "Telangana", "TN": "Tamil Nadu",
    "TR": "Tripura", "UP": "Uttar Pradesh", "WB": "West Bengal",
}


def category_state(category: str) -> str | None:
    """The state a CLAT category is reserved for, read from its official name or code, or None for an all-India category."""
    for spelling, state in STATE_SPELLINGS.items():
        if spelling in category:
            return state
    named = next((state for state in sorted(INDIAN_STATES, key=len, reverse=True) if state.lower() in category.lower()), None)
    if named:
        return named
    code = re.search(r"\(([A-Z0-9 &-]+)\)\s*$", category)
    return next((STATE_CODES[part] for part in re.split(r"[-\s]+", code.group(1)) if part in STATE_CODES), None) if code else None


KEA_HEADER = ["SL.NO", "All India Rank", "Course Code", "Name of the College Allotted.", "Course Name", "Allotted Category", "Course fees _", "Status"]


def kea_records(path: Path, round_label: str, url: str) -> tuple[list[dict], dict]:
    """The highest All India rank KEA allotted in each course and category in one round's final list, with KEA's course fee.

    Every row must sit in a table under KEA's header, and serial numbers must run from 1 with no gap.
    """
    last: dict[tuple[str, str], dict] = {}
    serials: list[int] = []
    blank = fee_conflicts = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                for row, cell_boxes in zip(table.extract(), table.rows):
                    cells = [clean(c) for c in row]
                    if cells[0] == "SL.NO":
                        if cells != KEA_HEADER:
                            raise SystemExit(f"Unexpected KEA header in {path}: {cells}")
                        continue
                    if not any(cells):
                        blank += 1
                        continue
                    serial, rank, code, college, course, category, fee, _status = cells
                    if not (serial.isdigit() and rank.isdigit() and re.fullmatch(r"[A-Z]\d{3}[A-Z]{2}", code) and fee.isdigit()):
                        raise SystemExit(f"Unexpected KEA row in {path}: {cells}")
                    serials.append(int(serial))
                    key = (code, category)
                    if key in last and last[key]["fee"]["declared"][0]["value"] != fee:
                        fee_conflicts += 1
                    if key not in last or int(rank) > last[key]["value"]:
                        # KEA wraps long names mid-word, as in "Bang" then "alore". The page text keeps the space before
                        # a wrap between words, so joining its lines with nothing restores both kinds of wrap.
                        box = cell_boxes.cells[3]
                        college = clean(page.get_textbox(box).replace("\n", "")) if box else college
                        last[key] = {
                            # KEA joins a college's name and address with a comma, and empty address parts with two.
                            "institute": re.sub(r",(?=\S)", ", ", re.sub(r",{2,}", ",", college)).strip(" ,"),
                            "programme": course, "programme_code": code, "group": f"Karnataka quota · {round_label}",
                            "category": category, "value": int(rank), "count": last.get(key, {}).get("count", 0),
                            "fee": {
                                "title": "Course fee listed by KEA", "note": "As printed in KEA's allotment list for this round, in rupees.",
                                "declared": [{"label": "Course fee (₹)", "value": fee}], "source_url": url, "year": "2026", "status": "official",
                            },
                        }
                    last[key]["count"] += 1
    if serials != list(range(1, len(serials) + 1)):
        raise SystemExit(f"KEA serial numbers in {path} skip or repeat")
    return list(last.values()), {"source_rows": len(serials), "blank_rows": blank, "fee_conflicts": fee_conflicts, "sequence_breaks": 0}


KEA_BASE = "https://cetonline.karnataka.gov.in/keawebentry456/ugneet2026/"
# KEA's final allotment list for each round, by the name we save it under in --kea's folder, and KEA's own file name.
KEA_LISTS = [
    ("Round 1", "r1-med-final", "UGNEET_ALLOT_2026_2nd_M_Fin_28082026kannada.pdf", "Medical, first round final allotment list, 28-08-2026"),
    ("Round 1", "r1-den-final", "UGNEET_ALLOT_2026_2nd_D_Fin_28082026kannada.pdf", "Dental, first round final allotment list, 28-08-2026"),
    ("Round 2", "r2-med-final", "UGNEET_ALLOT_2026_2nd_MFINAL_16092026_R2_SECONDkannada.pdf", "Medical, second round final allotment list, 16-09-2026"),
    ("Round 2", "r2-den-final", "UGNEET_ALLOT_2026_2nd_DFINAL_16092026_R2_SECONDkannada.pdf", "Dental, second round final allotment list, 16-09-2026"),
    ("Round 3", "r3-med-final", "UGNEET_ALLOT_2026_3rd_MFINAL_06102026_R3kannada.pdf", "Medical, third round final allotment list, 06-10-2026"),
    ("Round 3", "r3-den-final", "UGNEET_ALLOT_2026_3rd_DFINAL_06102026_R3kannada.pdf", "Dental, third round final allotment list, 06-10-2026"),
    ("Stray round", "stray-med-final", "UGNEET_ALLOT_2026_MED_STRAYkannada.pdf", "Medical, stray vacancy round final allotment list, 22-10-2026"),
    ("Stray round", "stray-den-final", "UGNEET_ALLOT_2026_DEN_STRAYkannada.pdf", "Dental, stray vacancy round final allotment list, 22-10-2026"),
]


def kea_route(folder: Path) -> dict:
    records, check = [], {}
    for round_label, name, source, _ in KEA_LISTS:
        found, file_check = kea_records(folder / f"{name}.pdf", round_label, KEA_BASE + source)
        records += found
        check[name] = file_check
    # A college's course codes share their first four characters. Use the name KEA prints most often for each college.
    names: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        names[record["programme_code"][:4]][record["institute"]] += 1
    for record in records:
        record["institute"] = names[record["programme_code"][:4]].most_common(1)[0][0]
    return {
        "code": "karnataka-neet", "stream": "Medical", "level": "UG", "name": "NEET UG Karnataka state quota (KEA)", "authority": "Karnataka Examinations Authority",
        "compare_requires_group": True, "rounds": ["Round 1", "Round 2", "Round 3", "Stray round"], "default_group": "Karnataka quota · Round 3", "default_programme": "MBBS-GOVT.",
        "metric": {"label": "NEET UG rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "Last rank allotted", "second_label": None},
        "document": document("UGNEET 2026 final allotment lists, rounds 1 to 3 and stray round", KEA_BASE + KEA_LISTS[4][2], "2026", "Rounds 1, 2 and 3, and stray round", "derived"),
        "sources": [{"title": f"KEA UGNEET 2026, {title}", "url": KEA_BASE + source} for _, _, source, title in KEA_LISTS],
        "limits": [
            "Karnataka's state quota is only for candidates eligible under KEA's rules. Check the KEA information bulletin before relying on these figures.",
            "Calculated by us from KEA's final allotment lists: the highest All India rank allotted in each course and category in that round. KEA doesn't publish these as cutoffs.",
            "Category codes are shown as KEA prints them. KEA's information bulletin explains each one.",
            "Course fees are shown as KEA prints them in each list.",
            "NIRF ranks aren't matched for this route yet, so the list orders colleges by how contested their seats were.",
        ],
        "check": check, "records": records,
    }


CCMT_ROUNDS = ["Round 1", "Round 2", "Round 3", "Special Round 1", "Special Round 2", "National Spot Round"]


def ccmt_records(path: Path) -> tuple[list[dict], dict]:
    """Every row of CCMT's 2025 maximum and minimum GATE score table, as saved from its public page.

    The page lists rows in its own order. Round 1 prints groups as G1, later rounds as Group 1, so both read as Group N.
    The page repeats some rows exactly, and a repeat adds nothing, so each is kept once.
    """
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved["header"] != ["SNo.", "Round", "Institute", "PG Program", "Group", "Category", "Max GATE Score", "Min GATE Score"]:
        raise SystemExit(f"Unexpected CCMT header: {saved['header']}")
    records, seen = [], set()
    for round_label, institute, programme, group, category, highest, lowest in saved["rows"]:
        if round_label not in CCMT_ROUNDS or not re.fullmatch(r"(G|Group )\d", group):
            raise SystemExit(f"Unexpected CCMT row: {round_label}, {group}")
        key = (round_label, institute, programme, group, category, highest, lowest)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "institute": institute.strip(), "programme": programme.strip(),
            "group": f"Group {group[-1]} · {round_label}", "category": category.strip(),
            "value": int(lowest), "second_value": int(highest),
        })
    order = {label: i for i, label in enumerate(CCMT_ROUNDS)}
    records.sort(key=lambda r: (order[r["group"].rsplit(" · ", 1)[1]], r["group"], r["institute"], r["programme"], r["category"]))
    return records, {"source_rows": len(saved["rows"]), "repeated_rows": len(saved["rows"]) - len(records), "sequence_breaks": 0}


def document(title: str, url: str, year: str, round_label: str, status: str) -> dict:
    return {"title": title, "url": url, "year": year, "round": round_label, "retrieved": RETRIEVED, "status": status}


# MCC labels its Round 1 file "Revised Provisional Result II", so the round says so wherever it's shown.
ROUND_1 = "Round 1 (provisional)"
CLAT_LIST = "https://clat2026.consortiumofnlus.ac.in/clat-2026/fifth-list.html"
MCC_SOURCES = [
    {"title": "NEET-UG Counselling Seats Allotment 2026, Round 1 (revised provisional result II)", "url": "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/08/20260824777992744.pdf"},
    {"title": "NEET-UG Counselling Seats Allotment 2026, Round 2 (final result)", "url": "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/09/20260912351980769.pdf"},
    {"title": "NEET-UG Counselling Seats Allotment 2026, Round 3 (final allotment result)", "url": "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/10/202610011801857474.pdf"},
    {"title": "NEET-UG Counselling Seats Allotment 2026, Stray Round (final allotment result)", "url": "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/10/202610201457709919.pdf"},
]


def build(args: argparse.Namespace, existing: dict) -> dict:
    kept = {route["code"]: route for route in existing.get("routes", [])}
    neet, neet_check = [], {}
    rounds = [("Round 2", args.mcc_round2, mcc_round_records), ("Round 3", args.mcc_round3, mcc_round_records), ("Stray round", args.mcc_stray, mcc_records)]
    if args.mcc_round1:
        rounds.insert(0, (ROUND_1, args.mcc_round1, mcc_records))
    for label, path, reader in rounds:
        found, check = reader(path, label)
        neet += found
        neet_check[label] = check
    neet = tidy_quotas(neet, mcc_quota_key(args.mcc_stray))
    shorts = short_names([r["institute"] for r in neet])
    for record in neet:
        record["institute_short"] = shorts[record["institute"]]
    clat, clat_check = clat_all(args.clat)
    routes = [
        {
            "code": "neet-ug", "stream": "Medical", "level": "UG", "name": "NEET UG (All India counselling)", "authority": "Medical Counselling Committee",
            "compare_requires_group": True,
            "rounds": [label for label, _, _ in rounds],
            "default_group": "All India and Open Seat Quota (AIIMS, JIPMER) · Round 3",
            "asks_gender": True,
            "quota_requirements": NEET_QUOTA_REQUIREMENTS,
            # Both quotas are open to candidates from any state. MCC files AIIMS and JIPMER seats under Open Seat Quota.
            "combined_quotas": {"All India and Open Seat Quota (AIIMS, JIPMER)": ["All India", "Open Seat Quota"]},
            "metric": {"label": "NEET UG rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "Last rank allotted", "second_label": None},
            "document": document("NEET-UG Counselling Seats Allotment 2026, Rounds 1 to 3 and stray round", MCC_SOURCES[2]["url"], "2026", "Rounds 1 (provisional), 2 and 3, and stray round", "derived"),
            "sources": MCC_SOURCES,
            "limits": [
                "Each round is shown separately. Seats filled in Round 1 whose holders kept them don't reappear in later rounds, so some top colleges, such as AIIMS New Delhi, appear only in Round 1.",
                "Calculated by us from MCC's rank-wise allotments: the last rank allotted to each seat in that round. MCC doesn't publish these as cutoffs.",
                "Round 1 is from MCC's revised provisional result, the latest Round 1 file MCC published, so it's labelled provisional.",
                "Excludes the 85% state quota, which each state runs separately.",
                "Some quotas, such as NRI, ESI and minority quotas, have their own eligibility rules, so choose a quota you qualify for.",
            ],
            "check": neet_check, "records": neet,
        },
        {
            "code": "clat", "stream": "Law", "level": "UG", "name": "CLAT UG (National Law Universities)", "authority": "Consortium of National Law Universities",
            "metric": {"label": "CLAT All India Rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "AIR cut-off", "second_label": "Category rank cut-off"},
            "document": document("Provisional 5th List, CLAT 2026 UG, cut-off tables for each university", CLAT_LIST, "2026", "Fifth provisional list", "official"),
            "limits": [
                "The fifth provisional list of 2026, as labelled by the Consortium. Later changes aren't included.",
                "Each category has its own cut-off, and state domicile categories apply only to eligible candidates.",
            ],
            "category_states": {c: s for c in sorted({r["category"] for r in clat}) if (s := category_state(c))},
            "check": clat_check, "records": clat,
        },
    ]
    if args.ccmt:
        ccmt, ccmt_check = ccmt_records(args.ccmt)
        routes.append({
            "code": "gate-ccmt", "stream": "Engineering", "level": "PG", "name": "GATE to NIT M.Tech (CCMT)", "authority": "Centralized Counselling for M.Tech./M.Arch./M.Plan. Admissions",
            # Round 1 is the only round whose scores cover every allotted candidate, so the page opens on it.
            "compare_requires_group": True, "rounds": CCMT_ROUNDS, "default_group": "Group 1 · Round 1",
            "metric": {"label": "GATE score", "unit": "score", "lower_is_better": False, "max": 1000, "whole_number": True, "value_label": "Minimum GATE score", "second_label": "Maximum GATE score"},
            "document": document("Maximum and Minimum GATE Score of CCMT 2025", "https://admissions.nic.in/admiss/admissions/orcrjacd/105012521", "2025", "All six rounds", "official"),
            "limits": [
                f"All {len({r['institute'] for r in ccmt})} institutes and six rounds of CCMT 2025, as CCMT publishes them. Each round is shown separately.",
                "For Special Round-I, Round-II and the National Spot Round, scores cover only candidates newly allotted or upgraded.",
                "Scores from different GATE papers and years may not compare directly. Check the group for your paper.",
            ],
            "check": ccmt_check, "records": ccmt,
        })
    else:
        routes.append(kept["gate-ccmt"])
    if args.maharashtra:
        maharashtra, mh_check, mh_rounds = [], {}, []
        for path in args.maharashtra:
            found, check = maharashtra_records(path)
            maharashtra += found
            mh_check[check["round"]] = check
            mh_rounds.append(check["round"])
        if mh_rounds != sorted(mh_rounds, key=lambda label: MH_ROUND_ORDER.index(label.split()[2].rstrip(",")) ):
            raise SystemExit(f"Give the Maharashtra files in round order, not {mh_rounds}")
        routes.append({
            "code": "maharashtra-engineering", "stream": "Engineering", "level": "UG", "name": "Maharashtra Engineering (CAP)", "authority": "State CET Cell, Maharashtra",
            "compare_requires_group": True, "rounds": mh_rounds, "default_group": f"State Level, Stage I · {mh_rounds[-1]}",
            "metric": {"label": "MHT-CET percentile", "unit": "percentile", "lower_is_better": False, "max": 100, "value_label": "Closing percentile", "second_label": "State merit number"},
            "document": document(f"Cut Off List for Maharashtra and Minority Seats, CAP Rounds {mh_rounds[0].split()[2].rstrip(',')} to {mh_rounds[-1].split()[2].rstrip(',')}, 2025-26", MH_SOURCES[-1]["url"], "2025-26", ", ".join(r.split(",")[0] for r in mh_rounds), "official"),
            "sources": MH_SOURCES[: len(mh_rounds)],
            "limits": [
                "Every CAP round of 2025-26, each shown separately with every stage as published.",
                "Seat codes are shown as published: G means General, L means Ladies, and the last letter means S state level, H home university or O other than home university.",
                "Excludes All India seats, which have a separate list.",
            ],
            "check": mh_check, "records": maharashtra,
        })
    else:
        routes.append(kept["maharashtra-engineering"])
    if args.kea:
        routes.append(kea_route(args.kea))
    elif "karnataka-neet" in kept:
        routes.append(kept["karnataka-neet"])
    return {"routes": routes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("mcc-stray", "mcc-round2", "mcc-round3"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--mcc-round1", type=Path)
    parser.add_argument("--clat", type=Path, nargs="+", required=True)
    parser.add_argument("--maharashtra", type=Path, nargs="+", help="One cut-off PDF per CAP round, in round order")
    parser.add_argument("--ccmt", type=Path)
    parser.add_argument("--kea", type=Path, help="Folder holding KEA's final allotment lists, named as in KEA_LISTS")
    data = build(parser.parse_args(), json.loads(OUT.read_text()) if OUT.exists() else {})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data))
    for route in data["routes"]:
        print(route["code"], len(route["records"]), route["check"])
