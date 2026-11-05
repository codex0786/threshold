"""Parse raw JoSAA HTML into plain rows. No database access and no network."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

EXPECTED_HEADER = ["Institute", "Academic Program Name", "Quota", "Seat Type", "Gender", "Opening Rank", "Closing Rank"]
_RANK = re.compile(r"^(\d+)(P?)(?:\.0+)?$")
_PROGRAMME = re.compile(r"^(?P<name>.*?)\s*\((?P<years>\d+)\s*Years?,\s*(?P<degree>.+)\)\s*$", re.S)


class SourceFormatError(ValueError):
    """The source table no longer has the structure this parser understands."""


@dataclass(frozen=True)
class RawRow:
    institute: str
    programme: str
    quota: str
    seat_type: str
    gender: str
    opening: str
    closing: str


def clean(text: str) -> str:
    return " ".join(text.split())


def parse_table(html: str) -> list[RawRow]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.select("table")
    if not tables:
        raise SourceFormatError("No table found in source document")
    table = max(tables, key=lambda t: len(t.select("tr")))
    rows = table.select("tr")
    header = [clean(c.text) for c in rows[0].select("th,td")]
    if header != EXPECTED_HEADER:
        raise SourceFormatError(f"Unexpected header: {header}")
    out = []
    for row in rows[1:]:
        cells = [clean(c.text) for c in row.select("td")]
        if len(cells) == 7 and cells[0]:
            out.append(RawRow(*cells))
    return out


def parse_file(path: Path) -> list[RawRow]:
    return parse_table(path.read_text(encoding="utf-8"))


def parse_rank(value: str) -> tuple[int | None, bool]:
    """Return (rank, is_preparatory). '50P' is a preparatory-course rank, a different list."""
    match = _RANK.match(value.strip())
    if not match:
        return None, False
    return int(match.group(1)), match.group(2) == "P"


def parse_programme(raw: str) -> tuple[str, int | None, str | None]:
    """Split 'Civil Engineering (4 Years, Bachelor of Technology)' into its parts."""
    match = _PROGRAMME.match(clean(raw))
    if not match:
        return clean(raw), None, None
    return match["name"].strip(), int(match["years"]), match["degree"].strip()
