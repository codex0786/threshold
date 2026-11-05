"""Read 'Placement & Higher Studies' tables from NIRF submissions published by institutes.

These figures are self-reported and cover all students in a programme level, such as
every 4-year UG student. They are institute-wide and never describe a single branch.
Extraction is conservative: anything unclear is reported and left out, never guessed.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

_YEAR = re.compile(r"^(20\d{2})-(\d{2})$")
_LEADING_INT = re.compile(r"^\s*(\d{4,8})")
_HEADER_WORDS = ("median", "placed")


@dataclass(frozen=True)
class OutcomeRow:
    graduation_year: int
    academic_year: str
    first_year_intake: int | None
    first_year_admitted: int | None
    graduating_students: int | None
    students_placed: int | None
    median_salary_inr: int | None
    median_salary_raw: str
    higher_studies_students: int | None
    page: int


_WORD_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_WORD_UNITS = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lakhs": 100000, "lac": 100000, "lacs": 100000, "crore": 10000000}


def _spell(word: str) -> str:
    """Institutes misspell these words ('Tenty', 'Laksh'), so close matches are accepted."""
    close = difflib.get_close_matches(word, [*_WORD_VALUES, *_WORD_UNITS], n=1, cutoff=0.8)
    return close[0] if close else word


def words_to_number(raw: str) -> int | None:
    """Read the amount written in words in brackets, e.g. '1700000(Seventeen Lakh)'."""
    match = re.search(r"\((.*)", raw or "")
    if not match:
        return None
    total = current = 0
    seen = False
    for token in re.sub(r"[^a-z ]", " ", match.group(1).lower()).split():
        word = _spell(token)
        if word in _WORD_VALUES:
            current += _WORD_VALUES[word]
            seen = True
        elif word == "hundred":
            current *= 100
        elif word in _WORD_UNITS:
            total += current * _WORD_UNITS[word]
            current = 0
    return total + current if seen else None


@dataclass
class Extraction:
    institute_name: str | None = None
    institute_code: str | None = None
    nirf_year: int | None = None
    category: str | None = None
    rows: list[OutcomeRow] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def squash(text: str | None) -> str:
    return re.sub(r"\s+", "", text or "")


def parse_count(value: str | None) -> int | None:
    text = squash(value).replace(",", "")
    return int(text) if text.isdigit() else None


def parse_median(value: str | None) -> int | None:
    """NIRF writes medians as '1700000(Seventeen Lakh)'. Only the leading digits are used."""
    match = _LEADING_INT.match((value or "").replace(",", ""))
    return int(match.group(1)) if match else None


def graduation_year(academic_year: str) -> int | None:
    match = _YEAR.match(squash(academic_year))
    return int(match.group(1)) + 1 if match else None


def looks_like_outcomes_table(rows: list[list[str | None]]) -> bool:
    if not rows or len(rows[0]) != 10:
        return False
    header = squash(" ".join(c or "" for c in rows[0])).lower()
    # NIRF headers are rotated, so letters arrive out of order. Data shape decides instead.
    body = rows[1:]
    if not body or graduation_year(body[0][5] or "") is None or graduation_year(body[0][0] or "") is None:
        return False
    return any(parse_median(r[8]) or "n/a" in squash(r[8]).lower() for r in body) or all(w in header for w in _HEADER_WORDS)


def rows_from_table(rows: list[list[str | None]], page: int) -> tuple[list[OutcomeRow], list[str]]:
    out, problems = [], []
    for cells in rows[1:]:
        grad = graduation_year(cells[5] or "")
        if grad is None:
            problems.append(f"Page {page}: unreadable year {cells[5]!r}")
            continue
        row = OutcomeRow(
            graduation_year=grad, academic_year=squash(cells[5]), first_year_intake=parse_count(cells[1]),
            first_year_admitted=parse_count(cells[2]), graduating_students=parse_count(cells[6]),
            students_placed=parse_count(cells[7]), median_salary_inr=parse_median(cells[8]),
            median_salary_raw=" ".join((cells[8] or "").split()), higher_studies_students=parse_count(cells[9]), page=page,
        )
        out.append(row)
        problems.extend(sanity_problems(row))
    return out, problems


def sanity_problems(row: OutcomeRow) -> list[str]:
    problems = []
    label = f"Page {row.page}, {row.academic_year}"
    if row.students_placed is not None and row.graduating_students is not None and row.students_placed > row.graduating_students:
        problems.append(f"{label}: placed {row.students_placed} exceeds graduating {row.graduating_students}")
    if row.median_salary_inr is not None and not 100_000 <= row.median_salary_inr <= 10_000_000:
        problems.append(f"{label}: median {row.median_salary_inr} is outside the plausible range")
    if row.median_salary_inr is None and row.median_salary_raw and "n/a" not in row.median_salary_raw.lower():
        problems.append(f"{label}: unreadable median {row.median_salary_raw!r}")
    written = words_to_number(row.median_salary_raw)
    if row.median_salary_inr is not None and written is not None and written != row.median_salary_inr:
        problems.append(f"{label}: digits {row.median_salary_inr} disagree with words {row.median_salary_raw!r}")
    return problems


def extract(path: Path) -> Extraction:
    """Return the UG 4-year outcomes. In the NIRF layout this is the first outcomes table in the document."""
    result = Extraction()
    with pymupdf.open(path) as document:
        full = "\n".join(page.get_text() for page in document)
        squashed = squash(full)
        name = re.search(r"InstituteName:(.+?)\[(IR-[A-Z]-[A-Z]-\d+)\]", squashed)
        if name:
            result.institute_name, result.institute_code = name.group(1), name.group(2)
        year = re.search(r"(?:SubmittedInstituteDataforNIRF|DataSubmittedbyInstitutionforIndiaRankings)'?(20\d{2})", squashed)
        if year:
            result.nirf_year = int(year.group(1))
        category = re.search(r"DataCapturingSystem:([A-Z&]+?)(?:Submitted|Data|Institute)", squashed)
        code = result.institute_code or ""
        code_categories = {"E": "Engineering", "O": "Overall", "U": "University", "R": "Research", "I": "Innovation", "M": "Management", "A": "Architecture", "B": "Sustainability", "C": "College", "P": "Pharmacy"}
        if len(code) > 3 and code[3] in code_categories:
            result.category = code_categories[code[3]]
        elif category:
            result.category = category.group(1).title()
        for index, page in enumerate(document):
            for table in page.find_tables().tables:
                rows = table.extract()
                if looks_like_outcomes_table(rows):
                    above = pymupdf.Rect(0, max(0, table.bbox[1] - 45), page.rect.width, table.bbox[1])
                    title = squash(page.get_text(clip=_unrotated(page, above))).lower()
                    if title and "ug[4" not in title and "ug4" not in title:
                        result.problems.append(f"Page {index + 1}: first outcomes table title is {title[:60]!r}, not UG 4-year")
                        return result
                    result.rows, problems = rows_from_table(rows, index + 1)
                    result.problems.extend(problems)
                    return result
    result.problems.append("No outcomes table found")
    return result


def _unrotated(page: pymupdf.Page, rect: pymupdf.Rect) -> pymupdf.Rect:
    # find_tables reports coordinates in the rotated view, while clip expects page space.
    return rect * page.derotation_matrix if page.rotation else rect
