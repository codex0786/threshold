"""Download JoSAA opening/closing rank tables from the official public forms.

The pages are public ASP.NET forms with no login or CAPTCHA. We request one
"ALL" table per year and round, wait between requests, and keep the raw HTML
untouched so that parsing can be re-run without contacting the source again.

Usage: python -m ingest.josaa_fetch --years 2021-2025 --current
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ARCHIVE_URL = "https://josaa.admissions.nic.in/applicant/seatmatrix/openingclosingrankarchieve.aspx"
CURRENT_URL = "https://josaa.admissions.nic.in/applicant/SeatAllotmentResult/CurrentORCR.aspx"
PREFIX = "ctl00$ContentPlaceHolder1$"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "josaa"
DELAY_SECONDS = 2.0
USER_AGENT = "Threshold-data-ingest/0.1 (education research; low-volume)"


class Form:
    """Walks the cascading dropdowns of a JoSAA form, one postback per field."""

    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.values: dict[str, str] = {}
        self._absorb(self.session.get(url, timeout=60).text)

    def _absorb(self, html: str) -> None:
        self.soup = BeautifulSoup(html, "html.parser")
        self.hidden = {
            i["name"]: i.get("value", "")
            for i in self.soup.select("input[type=hidden]")
            if i.get("name")
        }

    def field_name(self, suffix: str) -> str:
        for sel in self.soup.select("select"):
            if sel.get("name", "").lower() == (PREFIX + suffix).lower():
                return sel["name"]
        raise KeyError(f"Form field not found: {suffix}. The source page layout may have changed.")

    def options(self, suffix: str) -> list[str]:
        sel = self.soup.find("select", attrs={"name": self.field_name(suffix)})
        return [o.get("value") for o in sel.select("option") if o.get("value") not in ("0", "", None)]

    def choose(self, suffix: str, value: str) -> None:
        name = self.field_name(suffix)
        self.values[name] = value
        time.sleep(DELAY_SECONDS)
        data = {**self.hidden, **self.values, "__EVENTTARGET": name, "__EVENTARGUMENT": ""}
        response = self.session.post(self.url, data=data, timeout=60)
        response.raise_for_status()
        self._absorb(response.text)

    def submit(self) -> str:
        time.sleep(DELAY_SECONDS)
        data = {**self.hidden, **self.values, "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                PREFIX + "btnSubmit": "Submit"}
        response = self.session.post(self.url, data=data, timeout=180)
        response.raise_for_status()
        return response.text


def fetch_table(url: str, year: int | None, round_no: str) -> str:
    form = Form(url)
    if year is not None:
        form.choose("ddlYear", str(year))
    form.choose("ddlroundno", round_no)
    for suffix in ("ddlInstype", "ddlInstitute", "ddlBranch", "ddlSeatType"):
        form.choose(suffix, "ALL")
    return form.submit()


def available_rounds(url: str, year: int | None) -> list[int]:
    form = Form(url)
    if year is not None:
        form.choose("ddlYear", str(year))
    return sorted(int(v) for v in form.options("ddlroundno"))


def save(html: str, url: str, year: int, round_no: int, is_final: bool) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"orcr_{year}_r{round_no}.html"
    path.write_text(html, encoding="utf-8")
    meta = {
        "file": path.name, "url": url, "year": year, "round": round_no, "is_final_round": is_final,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
    }
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return meta


def fetch_year(url: str, query_year: int | None, year: int) -> None:
    rounds = available_rounds(url, query_year)
    if not rounds:
        print(f"{year}: no rounds offered")
        return
    final = max(rounds)
    for round_no in sorted({min(rounds), final}):
        if (RAW_DIR / f"orcr_{year}_r{round_no}.html").exists():
            print(f"{year} round {round_no}: already downloaded")
            continue
        html = fetch_table(url, query_year, str(round_no))
        meta = save(html, url, year, round_no, round_no == final)
        print(f"{year} round {round_no}/{final}: {len(html):,} bytes, sha {meta['sha256'][:10]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", default="2021-2025")
    parser.add_argument("--current", action="store_true", help="also fetch the current-year page")
    parser.add_argument("--current-year", type=int, default=2026)
    args = parser.parse_args()
    start, _, end = args.years.partition("-")
    for year in range(int(end or start), int(start) - 1, -1):
        fetch_year(ARCHIVE_URL, year, year)
    if args.current:
        fetch_year(CURRENT_URL, None, args.current_year)


if __name__ == "__main__":
    main()
