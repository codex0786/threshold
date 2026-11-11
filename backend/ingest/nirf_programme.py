"""Graduate outcomes for one programme level from NIRF submissions outside Engineering, such as Law's
UG [5 Years Program(s)] or Medical's MBBS table.

Two independent readings are taken: the table reader in ingest.nirf_pdf, and a reading of the document's text.
A year is kept only when the readings agree on it, or when only the text has it, because the table reader can
drop rows where a table splits. Each median must also match the amount written in words.

Usage: python -m ingest.nirf_programme data/raw/nirf_law "ug[5years" data/import/nlu_outcomes.json
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from ingest.nirf_pdf import extract, parse_median, squash, words_to_number

_ROW = re.compile(
    r"(\d{4}-\d{2})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d{4}-\d{2})\s*\|\s*(\d+)\s*\|\s*(\d{4}-\d{2})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
    r"\s*([^|]*?(?:\([^)]*\)|N/?A|-|0)[^|]*?(?:\|[^|]*?\))?)\s*\|\s*(\d+)"
)


@dataclass
class Year:
    academic_year: str
    first_year_intake: int | None
    graduating_students: int | None
    students_placed: int | None
    median_salary_inr: int | None
    median_salary_raw: str
    higher_studies_students: int | None
    notes: list[str] = field(default_factory=list)


@dataclass
class Document:
    file: str
    institute_name: str | None
    institute_code: str | None
    nirf_year: int | None
    category: str | None
    years: list[Year]
    problems: list[str]


def section(text: str, heading: str) -> str:
    """The text of one outcomes table, from its heading to the next table's heading."""
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading):]
    end = re.search(r"(?:UG|PG|PG-Integrated)\s*\[[^\]]*\]\s*:\s*Placement|UG3|Ph\.D Student Details", rest)
    return rest[: end.start()] if end else rest


def text_rows(text: str, heading: str) -> list[Year]:
    body = " | ".join(line.strip() for line in section(text, heading).splitlines() if line.strip())
    rows = []
    for m in _ROW.finditer(body):
        raw = " ".join(m.group(9).replace("|", " ").split())
        rows.append(Year(m.group(6), int(m.group(2)), int(m.group(7)), int(m.group(8)), parse_median(raw), raw, int(m.group(10))))
    return rows


def read(path: Path, title_mark: str, heading: str) -> Document:
    table = extract(path, title_mark)
    with pymupdf.open(path) as document:
        text = "\n".join(page.get_text() for page in document)
    from_text = {y.academic_year: y for y in text_rows(text, heading)}
    from_table = {squash(r.academic_year): r for r in table.rows}
    problems = [p for p in table.problems if "disagree with words" not in p]
    years = []
    for academic_year in sorted(set(from_text) | set(from_table)):
        t, r = from_text.get(academic_year), from_table.get(academic_year)
        if t is None:
            problems.append(f"{academic_year}: only the table reader found this year, so it's left out")
            continue
        if r is not None:
            pairs = [("graduating", t.graduating_students, r.graduating_students), ("placed", t.students_placed, r.students_placed),
                     ("median", t.median_salary_inr, r.median_salary_inr), ("higher studies", t.higher_studies_students, r.higher_studies_students)]
            differ = [name for name, a, b in pairs if a != b]
            if differ:
                problems.append(f"{academic_year}: the two readings disagree on {', '.join(differ)}, so it's left out")
                continue
        written = words_to_number(t.median_salary_raw)
        if t.median_salary_inr is not None and written is not None and written != t.median_salary_inr:
            t.notes.append(f"The median is printed as {t.median_salary_raw!r}, whose digits and words disagree, so it isn't shown")
            t.median_salary_inr = None
        if t.students_placed is not None and t.graduating_students is not None and t.students_placed > t.graduating_students:
            problems.append(f"{academic_year}: placed exceeds graduating, so it's left out")
            continue
        years.append(t)
    name = table.institute_name
    if name is None:
        # Some layouts put the ID on its own line, so the table reader misses the name. Read the labelled line instead.
        found = re.search(r"Institute Name:\s*(.+?)\s*(?:\[|\n)", text)
        name = squash(found.group(1)) if found else None
    return Document(path.name, name, table.institute_code, table.nirf_year, table.category, years, problems)


def main() -> None:
    folder, title_mark, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    heading = {"ug[5years": "UG [5 Years Program(s)]: Placement"}[title_mark]
    out = [asdict(read(p, title_mark, heading)) for p in sorted(folder.glob("*.pdf"))]
    output.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
