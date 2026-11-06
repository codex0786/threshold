"""Download and parse the JoSAA seat matrix. The page is a public form with no login or CAPTCHA.

Usage: python -m ingest.seat_matrix [--year 2026]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from ingest.josaa_fetch import Form
from ingest.josaa_parse import SourceFormatError, clean

URL = "https://josaa.admissions.nic.in/applicant/seatmatrix/seatmatrixinfo.aspx"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "josaa"
SEAT_COLUMNS = ("OPEN", "OPEN-PwD", "EWS", "EWS-PwD", "SC", "SC-PwD", "ST", "ST-PwD", "OBC-NCL", "OBC-NCL-PwD")
_STATE_NAMES = {
    "DELHI (NCT)": "Delhi", "CHANDIGARH (UT)": "Chandigarh", "PUDUCHERRY (UT)": "Puducherry",
    "ANDAMAN & NICOBAR ISLANDS (UT)": "Andaman and Nicobar Islands", "DAMAN & DIU (UT)": "Daman and Diu",
    "DADRA & NAGAR HAVELI (UT)": "Dadra and Nagar Haveli", "LAKSHADWEEP (UT)": "Lakshadweep",
    "JAMMU & KASHMIR (UT)": "Jammu and Kashmir", "LADAKH (UT)": "Ladakh",
}


@dataclass(frozen=True)
class SeatRow:
    institute: str
    programme: str
    quota: str
    states: tuple[str, ...]
    gender_pool: str
    seats: dict[str, int]


def state_name(raw: str) -> str:
    """Convert 'TAMIL NADU' or 'DELHI (NCT)' to the state names used everywhere else."""
    text = clean(raw)
    if text in _STATE_NAMES:
        return _STATE_NAMES[text]
    return " ".join(w if w == "and" else w.capitalize() for w in text.lower().split())


def _counts(cells: list[Tag]) -> dict[str, int]:
    values = [clean(c.get_text()) for c in cells[:len(SEAT_COLUMNS)]]
    if len(values) != len(SEAT_COLUMNS) or not all(v.isdigit() for v in values):
        raise SourceFormatError(f"Unexpected seat cells: {values}")
    return {name: int(v) for name, v in zip(SEAT_COLUMNS, values)}


def parse(html: str) -> list[SeatRow]:
    """Each programme and quota takes two table rows: gender-neutral seats, then female-only seats.

    The page's own grand totals are compared with the rows, so a shifted column stops the load.
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[SeatRow] = []
    for tr in soup.select("tr"):
        name = tr.select_one("span#lblnm")
        if name is None:
            continue
        label = clean(tr.select_one("span#lblQuota").get_text())
        states = tuple(state_name(s.get_text()) for s in tr.select("span[id^=lblstate]") if clean(s.get_text()))
        quota = {"All India": "AI", "Other than": "OS", "JK": "JK", "LA": "LA", "": "HS"}.get(label)
        if quota is None:
            raise SourceFormatError(f"Unknown quota label: {label!r}")
        institute, programme = clean(name.get_text()), clean(tr.select_one("span#lblAcademicProgram").get_text())
        cells = tr.find_all("td", recursive=False)
        pool = clean(cells[3].get_text())
        if pool != "Gender-Neutral":
            raise SourceFormatError(f"Expected the gender-neutral row first, found {pool!r}")
        rows.append(SeatRow(institute, programme, quota, states, "neutral", _counts(cells[4:])))
        female = tr.find_next_sibling("tr")
        female_cells = female.find_all("td", recursive=False) if female else []
        if not female_cells or not clean(female_cells[0].get_text()).startswith("Female-only"):
            raise SourceFormatError(f"No female-only row after {institute}: {programme}")
        rows.append(SeatRow(institute, programme, quota, states, "female", _counts(female_cells[1:])))
    if not rows:
        raise SourceFormatError("No seat rows found. The source page layout may have changed.")
    _check_totals(soup, rows)
    return rows


def _check_totals(soup: BeautifulSoup, rows: list[SeatRow]) -> None:
    for tr in soup.select("tr"):
        cells = [clean(c.get_text(" ")) for c in tr.find_all("td", recursive=False)]
        if "Total Seats" in cells:
            published = [int(v) for v in cells[cells.index("Total Seats") + 1:][:len(SEAT_COLUMNS)]]
            summed = [sum(r.seats[c] for r in rows) for c in SEAT_COLUMNS]
            if published != summed:
                raise SourceFormatError(f"Seat rows add up to {summed}, but the page states {published}")
            return
    raise SourceFormatError("The page's seat totals were not found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()
    form = Form(URL)
    for select in form.soup.select("select"):
        form.values[select["name"]] = "0"  # The first option is ALL on this form.
    html = form.submit()
    rows = parse(html)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"seatmatrix_{args.year}.html"
    path.write_text(html, encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps({
        "file": path.name, "url": URL, "year": args.year, "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
    }, indent=2))
    print(f"{path.name}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
