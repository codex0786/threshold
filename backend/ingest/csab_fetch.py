"""Download CSAB special round opening and closing ranks from the public form.

The form offers only the current year. Raw HTML is kept so parsing can be re-run offline.
Usage: python -m ingest.csab_fetch [--year 2026]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ingest.josaa_fetch import Form
from ingest.josaa_parse import parse_table

URL = "https://admissions.nic.in/csabspl/Applicant/seatallotmentresult/currentorcr.aspx"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "csab"
# Seats for foreign and overseas candidates use other rank lists, so they aren't stored.
QUOTAS = {
    "All India": "AI", "Other State": "OS", "Home State": "HS", "Home State for Goa": "GO",
    "Jammu & Kashmir (UT)": "JK", "Ladakh (UT)": "LA",
}
SKIPPED_QUOTAS = {"DASA-CIWG", "DASA-Non CIWG"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    form = Form(URL)
    for round_no in sorted(int(v) for v in form.options("ddlroundno")):
        form = Form(URL)
        form.choose("ddlroundno", str(round_no))
        for suffix in ("ddlInstype", "ddlInstitute", "ddlBranch"):
            form.choose(suffix, "ALL")
        html = form.submit()
        rows = parse_table(html)
        path = RAW_DIR / f"csab_{args.year}_r{round_no}.html"
        path.write_text(html, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({
            "file": path.name, "url": URL, "year": args.year, "round": round_no,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(html.encode()).hexdigest(),
        }, indent=2))
        print(f"{path.name}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
