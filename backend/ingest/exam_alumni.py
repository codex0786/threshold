"""Count publicly documented people on Wikidata who list an institute beyond JEE as alma mater.

Usage: python -m ingest.exam_alumni
Writes data/import/exam_alumni.json, which ingest.exam_profiles reads. Same rules as ingest.wikidata_alumni:
an item is accepted only on an exact label or alias match, only aggregate counts are kept, never names or
identifiers, and this is a labelled sample, not the alumni network.

Medical colleges are matched at college level only. A university's item, such as Banaras Hindu University,
would count graduates of every faculty, so it isn't used for one of its colleges.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ingest import wikidata_alumni
from ingest.wikidata_alumni import collect, normalise

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "wikidata" / "exams"
OUTPUT = ROOT / "data" / "import" / "exam_alumni.json"
ROUTES = ROOT / "backend" / "snapshot" / "exam_routes.json"
MEDICAL_SITES = ROOT / "data" / "import" / "medical_wikidata_sites.json"
USER_AGENT = "ThresholdDataIngest/0.1 (https://github.com/codex0786/threshold; education research, low volume)"
SEARCH = "https://www.wikidata.org/w/api.php"
# Medical items found by exact NIRF name that are whole universities, not colleges.
UNIVERSITY_LEVEL = {
    "Banaras Hindu University", "Saveetha Institute of Medical and Technical Sciences", "Dr. D. Y. Patil Vidyapeeth, Pune",
    "Sri Ramachandra Institute of Higher Education and Research", "Kalinga Institute of Industrial Technology",
    "Aligarh Muslim University", "Jamia Hamdard",
}


def get(session: requests.Session, url: str, **params) -> requests.Response:
    for _ in range(6):
        response = session.get(url, params=params, timeout=40)
        if response.status_code != 429:
            time.sleep(2.0)
            return response
        time.sleep(min(max(int(response.headers.get("Retry-After", "60")), 30), 300))
    raise RuntimeError("still rate limited")


def exact_qid(session: requests.Session, names: list[str]) -> str | None:
    for name in names:
        hits = get(session, SEARCH, action="wbsearchentities", search=name, language="en", format="json", limit=7).json().get("search", [])
        found = {h["id"] for h in hits if normalise(h.get("label", "")) == normalise(name) or normalise((h.get("match") or {}).get("text", "")) == normalise(name)}
        if len(found) == 1:
            return found.pop()
    return None


def law_names(institute: str) -> list[str]:
    """Name variants to try, from the counselling document's own name: without the abbreviation, with and without the city."""
    bare = re.sub(r"\s*\([^)]*\)", "", institute).strip()
    variants = [bare, bare.rsplit(",", 1)[0].strip()]
    return list(dict.fromkeys(v for v in variants if v))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    wikidata_alumni.USER_AGENT = USER_AGENT
    data = json.loads(ROUTES.read_text())
    clat = next(r for r in data["routes"] if r["code"] == "clat")
    targets: dict[str, dict] = {}
    for institute in sorted({r["institute"] for r in clat["records"]}):
        if "Silvassa" in institute:
            continue  # A campus. The university's item would count all its graduates.
        qid = exact_qid(session, law_names(institute))
        targets[f"clat|{institute}"] = {"route": "clat", "match": institute, "qid": qid}
    medical = json.loads(MEDICAL_SITES.read_text())
    registry = __import__("yaml").safe_load((ROOT / "data" / "registry" / "nirf_2025_exam_routes.yaml").read_text())
    matches = {e["name"]: e["match"] for c in ("Medical", "Dental") for e in registry["lists"][c]["ranks"]}
    for name, found in medical.items():
        if found.get("qid") and name not in UNIVERSITY_LEVEL:
            targets[f"neet-ug|{matches[name]}"] = {"route": "neet-ug", "match": matches[name], "qid": found["qid"], "wikidata_label": found.get("label")}
    retrieved = datetime.now(timezone.utc).isoformat()
    out = []
    for key, target in targets.items():
        if not target["qid"]:
            out.append({**target, "sample_size": None})
            continue
        cache = RAW / f"{target['qid']}.json"
        if cache.exists():
            counts = json.loads(cache.read_text())
        else:
            counts = {"retrieved_at": retrieved, **collect(session, target["qid"])}
            cache.write_text(json.dumps(counts, indent=1))
        out.append({**target, **counts})
        print(f"{target['qid']}: {counts['sample_size']} people  {target['match'][:60]}", flush=True)
    OUTPUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{sum(1 for o in out if o['qid'])} of {len(out)} matched; {sum(1 for o in out if (o.get('sample_size') or 0) >= 30)} with 30 or more people")


if __name__ == "__main__":
    main()
