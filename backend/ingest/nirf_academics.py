"""Read faculty, doctoral, research and spending tables from accepted NIRF submissions.

Usage: python -m ingest.nirf_academics
Faculty tables name individuals and give their age and gender. Only totals leave this module:
no name, age, gender or date is returned or written. Figures cover the submission as a whole,
never a department, and are self-reported.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median

import pymupdf

from ingest.nirf_pdf import words_to_number

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "nirf"
OUTPUT = ROOT / "data" / "import" / "academics_nirf.csv"
REPORT = ROOT / "data" / "import" / "academics_nirf_report.json"
_YEAR = re.compile(r"^\d{4}(-\d{2})?$")
FIELDS = (
    "institution_slug", "submission_year", "category", "academic_year", "faculty_listed", "faculty_current", "faculty_regular", "faculty_with_phd",
    "professors", "associate_professors", "assistant_professors", "median_experience_months", "students_total", "phd_students",
    "phd_graduated", "sponsored_projects", "sponsored_amount_inr", "consultancy_amount_inr", "patents_published", "patents_granted",
    "library_spend_inr", "equipment_spend_inr", "source_title", "source_url", "source_file", "problems",
)


@dataclass
class Faculty:
    listed: int = 0
    current: int = 0
    regular: int = 0
    with_phd: int = 0
    professors: int = 0
    associate: int = 0
    assistant: int = 0
    median_experience_months: int | None = None
    problems: list[str] = field(default_factory=list)


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _number(value: str | None) -> int | None:
    text = _clean(value)
    match = re.match(r"^(\d[\d,]*)(\.\d+)?\b", text)
    return int(match.group(1).replace(",", "")) if match else None


def summarise_faculty(rows: list[list[str]]) -> Faculty:
    """Count rows from Srno, Name, Age (may be blank), Designation, Gender, Qualification, Experience, Current, Joining, Leaving, Type."""
    out = Faculty(listed=len(rows))
    numbers = [_number(r[0]) for r in rows]
    if numbers != list(range(1, len(rows) + 1)):
        out.problems.append("Faculty row numbers aren't continuous, so rows may be missing")
    experience = []
    for row in rows:
        designation, qualification, months, current, kind = (_clean(row[i]).lower() for i in (3, 5, 6, 7, 10))
        if current != "yes":
            continue
        out.current += 1
        if kind != "regular":
            continue
        out.regular += 1
        # Only a stated doctorate counts, so "Ph.D (pursuing)" doesn't.
        if re.fullmatch(r"ph\.?\s?d\.?|d\.?\s?sc\.?|d\.?\s?phil\.?", qualification):
            out.with_phd += 1
        if designation.startswith("assistant professor"):
            out.assistant += 1
        elif designation.startswith("associate professor"):
            out.associate += 1
        elif designation.startswith(("professor", "dean", "director", "head")):
            out.professors += 1
        if months.isdigit():
            experience.append(int(months))
    out.median_experience_months = int(median(experience)) if experience else None
    return out


def _tables(document: pymupdf.Document) -> list[list[list[str]]]:
    found = []
    for page in document:
        for table in page.find_tables().tables:
            found.append(table.extract())
    return found


def _row(table: list | None, label: str) -> list[str] | None:
    for row in table or []:
        if _clean(row[0]).lower().startswith(label.lower()):
            return row
    return None


def read_document(path: Path) -> dict:
    with pymupdf.open(path) as document:
        tables = _tables(document)
        text = " ".join(_clean(p.get_text()) for p in document)
    problems: list[str] = []
    faculty_rows = []
    for table in tables:
        for row in table:
            # Some submissions leave out the age column.
            if len(row) == 10 and _number(row[0]) is not None and _clean(row[6]).lower() in ("yes", "no"):
                row = [row[0], row[1], None, *row[2:]]
            if len(row) == 11 and _number(row[0]) is not None and _clean(row[7]).lower() in ("yes", "no"):
                faculty_rows.append(row)
    faculty = summarise_faculty(faculty_rows)
    problems += faculty.problems
    if not faculty_rows:
        problems.append("No faculty table found")

    students = 0
    for table in tables:
        header = [_clean(c).lower() for c in table[0]] if table else []
        if "total students" in header:
            at = header.index("total students")
            students += sum(_number(r[at]) or 0 for r in table[1:] if _clean(r[0]).startswith(("UG", "PG")))

    phd_students = None
    match = re.search(r"Total Students Full Time (\d+) Part Time (\d+)", text)
    if match:
        phd_students = int(match[1]) + int(match[2])
    graduated: dict[str, int] = {}
    match = re.search(r"No\. of Ph\.D students graduated \(including Integrated Ph\.D\) (\d{4}-\d{2}) (\d{4}-\d{2}) (\d{4}-\d{2}) Full Time (\d+) (\d+) (\d+) Part Time (\d+) (\d+) (\d+)", text)
    if match:
        graduated = {match[i + 1]: int(match[i + 4]) + int(match[i + 7]) for i in range(3)}

    years: dict[str, dict] = {year: {"phd_graduated": n} for year, n in graduated.items()}
    for kind, key in (("Sponsored", "sponsored"), ("Consultancy", "consultancy")):
        block = re.search(rf"{kind} (?:Research|Project) Details Financial Year (\d{{4}}-\d{{2}}) (\d{{4}}-\d{{2}}) (\d{{4}}-\d{{2}}) Total no\. of {kind} Projects (\d+) (\d+) (\d+)", text)
        if not block:
            problems.append(f"{kind} table not found")
            continue
        labels = [block[1], block[2], block[3]]
        amount_table = next((t for t in tables if t and _clean(t[0][0]) == "Financial Year" and any(_clean(r[0]).startswith(f"Total no. of {kind}") for r in t)), None)
        amounts = _row(amount_table, "Total Amount Received")
        words = _row(amount_table, "Amount Received in Words")
        # A table split across pages isn't found whole, so read the same row from the text. There's no words check on this route.
        if not amounts:
            after = text[block.end():]
            found = re.search(r"Total Amount Received \(Amount in Rupees\) (\d+) (\d+) (\d+)", after[:400])
            amounts = ["", found[1], found[2], found[3]] if found else None
        for i, year in enumerate(labels):
            entry = years.setdefault(year, {})
            if key == "sponsored":
                entry["sponsored_projects"] = int(block[4 + i])
            amount = _number(amounts[i + 1]) if amounts and len(amounts) > i + 1 else None
            in_words = words_to_number(_clean(words[i + 1])) if words and len(words) > i + 1 else None
            if amount is not None and in_words is not None and amount != in_words:
                problems.append(f"{kind} {year}: digits {amount} disagree with words {in_words}")
                amount = None
            entry[f"{key}_amount_inr"] = amount
    match = re.search(r"Calendar year (\d{4}) (\d{4}) (\d{4}) No\. of Patents Published (\d+) (\d+) (\d+) No\. of Patents Granted (\d+) (\d+) (\d+)", text)
    if match:
        for i in range(3):
            # A calendar year is filed against the academic year it starts.
            label = f"{match[i + 1]}-{str(int(match[i + 1]) + 1)[2:]}"
            years.setdefault(label, {}).update(patents_published=int(match[4 + i]), patents_granted=int(match[7 + i]))
    capex = next((t for t in tables if t and "Academic Year" in _clean(t[0][0]) and any("Library" in _clean(r[0]) for r in t)), None)
    if capex:
        labels = [_clean(c) for c in capex[0][1:4]]
        for key, label in (("library_spend_inr", "Library"), ("equipment_spend_inr", "New Equipment")):
            row = _row(capex, label)
            for i, year in enumerate(labels):
                if row and len(row) > i + 1 and _YEAR.match(year):
                    years.setdefault(year, {})[key] = _number(row[i + 1])
    return {"faculty": faculty, "students_total": students or None, "phd_students": phd_students, "years": years, "problems": problems}


def main() -> None:
    report = json.loads((ROOT / "data" / "import" / "placements_nirf_report.json").read_text())["institutes"]
    rows, summary = [], {}
    for slug, entry in sorted(report.items()):
        if entry.get("status") != "extracted":
            continue
        result = read_document(RAW / entry["file"])
        faculty: Faculty = result["faculty"]
        summary[slug] = {"category": entry["category"], "year": entry["document_year"], "problems": result["problems"]}
        common = {
            "institution_slug": slug, "submission_year": entry["document_year"], "category": entry["category"],
            "source_title": f"NIRF {entry['document_year']} {entry['category']} submission, {slug}", "source_url": entry["url"],
            "source_file": f"data/raw/nirf/{entry['file']}", "problems": "; ".join(result["problems"]),
        }
        # One snapshot row for people, then one row per year for research and spending.
        rows.append({
            **common, "academic_year": "", "faculty_listed": faculty.listed, "faculty_current": faculty.current, "faculty_regular": faculty.regular,
            "faculty_with_phd": faculty.with_phd, "professors": faculty.professors, "associate_professors": faculty.associate,
            "assistant_professors": faculty.assistant, "median_experience_months": faculty.median_experience_months,
            "students_total": result["students_total"], "phd_students": result["phd_students"],
        })
        for year, values in sorted(result["years"].items(), reverse=True):
            rows.append({**common, "academic_year": year, **values})
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    REPORT.write_text(json.dumps(summary, indent=1))
    print(f"Wrote {len(rows)} rows from {len(summary)} documents, {sum(1 for v in summary.values() if v['problems'])} with problems")


if __name__ == "__main__":
    main()
