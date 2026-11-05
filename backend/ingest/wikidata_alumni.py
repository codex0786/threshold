"""Count publicly documented people on Wikidata who list an institute as alma mater.

Usage: python -m ingest.wikidata_alumni

Only aggregate counts are stored, never names or person identifiers. Wikidata records no
degree level and skews heavily to researchers, so this is a labelled sample. It is not the
alumni network and it says little about typical B.Tech graduates.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import AlumniObservation, AuditLog, DataSource, Institution, SourceDocument

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "wikidata"
QID_FILE = ROOT / "data" / "registry" / "wikidata_institutions.yaml"
SPARQL = "https://query.wikidata.org/sparql"
SEARCH = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Threshold-data-ingest/0.1 (education research; low-volume)"
DELAY_SECONDS = 2.0
TOP_N = 12


def normalise(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def find_qids(names: dict[str, list[str]]) -> dict[str, str]:
    """Accept a Wikidata item only if its label or alias exactly matches a known institute name."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    found: dict[str, str] = {}
    for slug, candidates in names.items():
        for name in candidates:
            response = session.get(SEARCH, params={"action": "wbsearchentities", "search": name, "language": "en", "format": "json", "limit": 5}, timeout=30)
            time.sleep(0.5)
            if not response.ok:
                continue
            target = normalise(name)
            for hit in response.json().get("search", []):
                terms = [hit.get("label", ""), (hit.get("match") or {}).get("text", "")]
                if any(normalise(term) == target for term in terms):
                    found[slug] = hit["id"]
                    break
            if slug in found:
                break
    return found


def query(session: requests.Session, sparql: str) -> list[dict]:
    for attempt in range(3):
        response = session.get(SPARQL, params={"query": sparql}, headers={"Accept": "application/sparql-results+json"}, timeout=70)
        if response.status_code == 429 or response.status_code >= 500:
            time.sleep(20 * (attempt + 1))
            continue
        response.raise_for_status()
        time.sleep(DELAY_SECONDS)
        return [{k: v["value"] for k, v in row.items()} for row in response.json()["results"]["bindings"]]
    raise RuntimeError("Wikidata did not respond")


def collect(session: requests.Session, qid: str) -> dict:
    total = query(session, f"SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE {{ ?p wdt:P69 wd:{qid} ; wdt:P31 wd:Q5 . }}")
    top = lambda prop: f"""SELECT ?label (COUNT(DISTINCT ?p) AS ?n) WHERE {{ ?p wdt:P69 wd:{qid} ; wdt:P31 wd:Q5 ; wdt:{prop} ?o . FILTER(?o != wd:{qid}) ?o rdfs:label ?label . FILTER(LANG(?label) = "en") }} GROUP BY ?label ORDER BY DESC(?n) ?label LIMIT {TOP_N}"""  # noqa: E731
    founders = query(session, f"SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE {{ ?p wdt:P69 wd:{qid} ; wdt:P31 wd:Q5 . ?org wdt:P112 ?p . }}")
    return {
        "sample_size": int(total[0]["n"]), "founders": int(founders[0]["n"]),
        "occupation": [{"label": r["label"], "count": int(r["n"])} for r in query(session, top("P106"))],
        "employer": [{"label": r["label"], "count": int(r["n"])} for r in query(session, top("P108"))],
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    institutions = yaml.safe_load((ROOT / "data" / "registry" / "institutions.yaml").read_text())
    if QID_FILE.exists():
        qids = yaml.safe_load(QID_FILE.read_text()) or {}
    else:
        names = {i["slug"]: list(dict.fromkeys([*i["names"], i["short"]])) for i in institutions if i["type"] in ("IIT", "IISC", "NIT", "IIIT") or i.get("website")}
        qids = find_qids(names)
        QID_FILE.write_text("# Exact name matches on Wikidata. Review before relying on them.\n" + yaml.safe_dump(qids, sort_keys=True))
    print(f"{len(qids)} institutes matched on Wikidata")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retrieved = datetime.now(timezone.utc)
    results = {}
    for slug, qid in sorted(qids.items()):
        cache = RAW / f"{slug}.json"
        if cache.exists():
            results[slug] = json.loads(cache.read_text())
            continue
        try:
            results[slug] = {"qid": qid, "retrieved_at": retrieved.isoformat(), **collect(session, qid)}
        except (requests.RequestException, RuntimeError) as error:
            print(f"{slug}: {type(error).__name__}")
            continue
        cache.write_text(json.dumps(results[slug], indent=1))
        print(f"{slug}: {results[slug]['sample_size']} people")
    with SessionLocal() as db:
        source = db.scalar(select(DataSource).where(DataSource.key == "wikidata_alumni"))
        institutes = {i.slug: i for i in db.scalars(select(Institution))}
        db.execute(delete(AlumniObservation).where(AlumniObservation.source_id == source.id))
        count = 0
        for slug, data in results.items():
            digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            document = db.scalar(select(SourceDocument).where(SourceDocument.source_id == source.id, SourceDocument.sha256 == digest))
            if document is None:
                document = SourceDocument(
                    source_id=source.id, title=f"Wikidata query for {institutes[slug].short_name} ({data['qid']})",
                    url=f"https://www.wikidata.org/wiki/{data['qid']}", raw_path=f"data/raw/wikidata/{slug}.json", sha256=digest,
                    fetched_at=datetime.fromisoformat(data["retrieved_at"]),
                )
                db.add(document)
                db.flush()
            rows = [("sample", "All documented people", data["sample_size"]), ("founder", "Listed as a founder of an organisation", data["founders"])]
            rows += [("occupation", r["label"], r["count"]) for r in data["occupation"]]
            rows += [("employer", r["label"], r["count"]) for r in data["employer"]]
            for dimension, category, value in rows:
                db.add(AlumniObservation(
                    institution_id=institutes[slug].id, dimension=dimension, category=category, people=value, sample_size=data["sample_size"],
                    source_id=source.id, source_document_id=document.id,
                ))
                count += 1
        db.add(AuditLog(actor="ingest.wikidata_alumni", action="load", entity="alumni_observations", detail={"institutes": len(results), "rows": count}))
        db.commit()
    print(f"Stored {count} aggregate rows for {len(results)} institutes. No names were stored.")


if __name__ == "__main__":
    main()
