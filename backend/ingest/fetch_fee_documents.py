"""Download the documents named in the import files, because raw storage stays out of git.

Usage: python -m ingest.fetch_fee_documents
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import requests

from ingest.nirf_fetch import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    for name in ("fees_official", "placements_branch_reports", "placement_sectors", "placement_recruiters"):
        with (ROOT / "data" / "import" / f"{name}.csv").open(newline="") as handle:
            for row in csv.DictReader(handle):
                path = ROOT / row["source_file"]
                if path.exists():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                response = requests.get(row["source_url"], headers={"User-Agent": USER_AGENT}, timeout=60)
                if response.status_code == 200 and response.content.startswith(b"%PDF"):
                    path.write_bytes(response.content)
                    print(f"Saved {path.name}")
                else:
                    print(f"Could not fetch {row['source_url']}: HTTP {response.status_code}")
                time.sleep(1.5)


if __name__ == "__main__":
    main()
