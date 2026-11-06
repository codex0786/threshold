"""Download institution-level research counts from the OpenAlex API. Free, open data (CC0).

Usage: python -m ingest.openalex_fetch
An institute is matched only when its name is identical to a name in institutions.yaml, so a
near-match never lends one institute another's numbers. Unmatched institutes stay blank.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import yaml

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "openalex"
OUTPUT = ROOT / "data" / "import" / "research_openalex.json"
URL = "https://api.openalex.org/institutions"
FIELDS = "id,ror,display_name,display_name_alternatives,works_count,cited_by_count,summary_stats,counts_by_year"
USER_AGENT = "Threshold-data-ingest/0.1 (education research; low-volume)"


def normalise(name: str) -> str:
    text = re.sub(r"\(.*?\)", " ", name.lower()).replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


def search(name: str) -> dict:
    query = urlencode({"search": name, "filter": "country_code:IN", "per-page": 5, "select": FIELDS})
    done = subprocess.run(["curl", "-sS", "-L", "-m", "60", "-A", USER_AGENT, f"{URL}?{query}"], capture_output=True, text=True)
    return json.loads(done.stdout)


def main() -> None:
    """One first-page search per institute, which needs no key. Stops if the free daily budget runs out."""
    RAW.mkdir(parents=True, exist_ok=True)
    earlier = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    raw_path = RAW / "institutions_in.json"
    matched, ambiguous, unmatched, not_tried = earlier.get("matched", {}), earlier.get("ambiguous", []), earlier.get("unmatched", []), []
    raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    stopped = False
    for entry in yaml.safe_load((ROOT / "data" / "registry" / "institutions.yaml").read_text()):
        # A run can stop at the free daily budget, so the next one carries on from there.
        if entry["slug"] in raw:
            continue
        if stopped:
            not_tried.append(entry["slug"])
            continue
        body = search(entry["names"][0])
        time.sleep(1.0)
        if "results" not in body:
            print("Stopping:", json.dumps(body)[:200])
            stopped = True
            not_tried.append(entry["slug"])
            continue
        raw[entry["slug"]] = body["results"]
        wanted = {normalise(n) for n in entry["names"]}
        found = {r["id"]: r for r in body["results"] if wanted & {normalise(n) for n in (r["display_name"], *(r.get("display_name_alternatives") or []))}}
        if len(found) == 1:
            record = next(iter(found.values()))
            years = {c["year"]: c["works_count"] for c in record.get("counts_by_year") or []}
            matched[entry["slug"]] = {
                "openalex_id": record["id"], "display_name": record["display_name"], "works_count": record["works_count"],
                "cited_by_count": record["cited_by_count"], "h_index": (record.get("summary_stats") or {}).get("h_index"),
                "works_by_year": {str(y): years[y] for y in sorted(years)[-6:]},
            }
        elif found:
            ambiguous.append(entry["slug"])
        else:
            unmatched.append(entry["slug"])
    text = json.dumps(raw)
    raw_path.write_text(text)
    OUTPUT.write_text(json.dumps({
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "url": URL, "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "raw_path": "data/raw/openalex/institutions_in.json", "matched": matched, "ambiguous": ambiguous, "unmatched": unmatched, "not_tried": not_tried,
    }, indent=1))
    print(f"Matched {len(matched)}, ambiguous {len(ambiguous)}, unmatched {len(unmatched)}, not tried {len(not_tried)}")


if __name__ == "__main__":
    main()
