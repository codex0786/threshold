"""Extract official documents for the admission routes beyond JEE.

Writes the git-ignored backend/snapshot/exam_routes.json. This repository is public, so don't commit it.
Candidate-level identifiers (such as CLAT admit card numbers) are never read
into the output.

Usage: python -m ingest.exam_extract --mcc a.pdf --clat b.pdf --maharashtra c.pdf --ccmt d.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parents[1] / "snapshot" / "exam_routes.json"
RETRIEVED = "2026-11-06"
CLAT_RESERVATION_END = "Note :"


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def mcc_records(path: Path) -> tuple[list[dict], dict]:
    """Group allotments into the last rank allotted. Each record is our calculation, not an MCC figure."""
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
                    # Some institute names in the source end with a contact email, which isn't part of the name.
                    key = (re.sub(r",?\s*\S+@\S+", "", clean(row[3])), clean(row[4]), clean(row[2]), clean(row[5]))
                    groups[key].append(int(rank))
    records = [
        {"institute": k[0], "programme": k[1], "group": k[2], "category": k[3], "value": max(v), "first_value": min(v), "count": len(v)}
        for k, v in groups.items()
    ]
    return records, {"source_rows": rows, "sequence_breaks": breaks}


def clat_records(path: Path) -> tuple[list[dict], dict]:
    """Read only the Cut-Off Rank Table. Rows holding admit card numbers are never parsed."""
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    institute = clean(re.search(r"Provisional 5th List.*?\n(.+?)\n", text).group(1))
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
                "institute": institute, "programme": "5-Year Integrated Law (UG)", "group": f"{section} reservation",
                "category": " ".join(words), "seats": int(seats),
                "value": None if air == "**" else int(air), "second_value": None if category_rank == "**" else int(category_rank),
                "note": "Deemed fulfilled, so no cut-off is given" if air == "**" else None,
            })
            label = []
    return records, {"source_rows": len(records), "sequence_breaks": 0}


MH_CELL = re.compile(r"^(\d+)\s*\((\d+(?:\.\d+)?)\)$")
MH_SECTION = re.compile(r"^(State Level|(Home University|Other Than Home University) Seats Allotted to .+)$")


def page_lines(page: pymupdf.Page) -> list[tuple[float, str]]:
    lines = [(line["bbox"][1], clean("".join(span["text"] for span in line["spans"]))) for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])]
    return sorted(line for line in lines if line[1])


def maharashtra_records(path: Path) -> tuple[list[dict], dict]:
    """Closing merit number and percentile for every published stage, under the seat codes as published.

    A course code starts with its institute's code, so the institute comes from the code, not page position.
    """
    records: list[dict] = []
    bad = unknown_institute = 0
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
                for index, row in enumerate(rows[1:], start=1):
                    stage = clean(row[0]) if has_stage_column else "I" * index
                    cells = zip(codes[1:], row[1:]) if has_stage_column else zip(codes, row)
                    for code, cell in cells:
                        cell = clean(cell)
                        if not cell:
                            continue
                        match = MH_CELL.match(cell)
                        if not match or stage not in ("I", "II") or not table_section or not code:
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
                records.append({
                    "institute": institutes[parent[1][:5]], "programme": parent[2], "programme_code": parent[1],
                    "group": f"{parent[3]}, Stage I", "category": code,
                    "value": float(match.group(2)) or None, "second_value": int(match.group(1)), "note": None,
                })
    return records, {"source_rows": len(records), "sequence_breaks": bad, "unknown_institute": unknown_institute}


def document(title: str, url: str, year: str, round_label: str, status: str) -> dict:
    return {"title": title, "url": url, "year": year, "round": round_label, "retrieved": RETRIEVED, "status": status}


def build(args: argparse.Namespace) -> dict:
    mcc, mcc_check = mcc_records(args.mcc)
    clat, clat_check = clat_records(args.clat)
    maharashtra, mh_check = maharashtra_records(args.maharashtra)
    ccmt = json.loads(args.ccmt.read_text())
    return {"routes": [
        {
            "code": "neet-ug", "stream": "Medical", "level": "UG", "name": "NEET UG (All India counselling)", "authority": "Medical Counselling Committee",
            "compare_requires_group": True,
            "metric": {"label": "NEET UG rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "Last rank allotted", "second_label": None},
            "document": document("NEET-UG Counselling Seats Allotment 2026, Stray Round (final allotment result)", "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/10/202610201457709919.pdf", "2026", "Stray vacancy round", "derived"),
            "limits": ["Covers the stray vacancy round only, so these are not the closing ranks of the main rounds.", "Calculated by us from rank-wise allotments. MCC does not publish these as cutoffs in this document.", "Excludes the 85% state quota, which each state runs separately.", "Some quotas, such as NRI, ESI and minority quotas, have their own eligibility rules, so choose a quota you qualify for."],
            "check": mcc_check, "records": mcc,
        },
        {
            "code": "clat", "stream": "Law", "level": "UG", "name": "CLAT UG (National Law Universities)", "authority": "Consortium of National Law Universities",
            "metric": {"label": "CLAT All India Rank", "unit": "rank", "lower_is_better": True, "whole_number": True, "value_label": "AIR cut-off", "second_label": "Category rank cut-off"},
            "document": document("Provisional 5th List, CLAT 2026 UG, National Law School of India University, Bengaluru", "https://s3.ap-south-1.amazonaws.com/files2026.consortiumofnlus.ac.in/list5/UG-NationalLawSchoolofIndiaUniversityNLSIUBengaluru-2026.pdf", "2026", "Fifth provisional list", "official"),
            "limits": ["One university only in this demo.", "The list is provisional, as labelled by the Consortium.", "Each category has its own cut-off, and Karnataka categories apply only to eligible candidates."],
            "check": clat_check, "records": clat,
        },
        {
            "code": "gate-ccmt", "stream": "Engineering", "level": "PG", "name": "GATE to NIT M.Tech (CCMT)", "authority": "Centralized Counselling for M.Tech./M.Arch./M.Plan. Admissions",
            "metric": {"label": "GATE score", "unit": "score", "lower_is_better": False, "max": 1000, "value_label": "Minimum GATE score", "second_label": "Maximum GATE score"},
            "document": document("Maximum and Minimum GATE Score of CCMT 2025", "https://admissions.nic.in/admiss/admissions/orcrjacd/105012521", "2025", "All rounds", "official"),
            "limits": [ccmt["scope"], "For Special Round-I, Round-II and the National Spot Round, scores cover only candidates newly allotted or upgraded.", "Scores from different GATE papers and years may not compare directly. Check the group for your paper."],
            "check": {"source_rows": len(ccmt["records"]), "sequence_breaks": 0}, "records": ccmt["records"],
        },
        {
            "code": "maharashtra-engineering", "stream": "Engineering", "level": "UG", "name": "Maharashtra Engineering (CAP)", "authority": "State CET Cell, Maharashtra",
            "metric": {"label": "MHT-CET percentile", "unit": "percentile", "lower_is_better": False, "max": 100, "value_label": "Closing percentile", "second_label": "State merit number"},
            "document": document("Cut Off List for Maharashtra and Minority Seats, CAP Round I, 2024-25", "http://fe2025.mahacet.org/2024/2024ENGG_CAP1_CutOff.pdf", "2024-25", "CAP Round I", "official"),
            "limits": ["Round I of 2024-25 only, with each stage shown as published. This sample has no later round or more recent year.", "Seat codes are shown as published: G means General, L means Ladies, and the last letter means S state level, H home university or O other than home university.", "Excludes All India seats, which have a separate list."],
            "check": mh_check, "records": maharashtra,
        },
    ]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("mcc", "clat", "maharashtra", "ccmt"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    data = build(parser.parse_args())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data))
    for route in data["routes"]:
        print(route["code"], len(route["records"]), route["check"])
