"""Institute profiles for the routes beyond JEE: official website, graduate outcomes, faculty and research,
and fees, each with its source. Rewrites backend/snapshot/exam_routes.json in place, under `profiles`.

Usage: python -m ingest.exam_profiles
Run after ingest.exam_extract, ingest.mcc_fees and ingest.exam_rankings. Stops if a registry entry matches no
institute, or a NIRF document doesn't print the expected institute name, so nothing attaches to the wrong place.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import yaml

from ingest.nirf_academics import read_document
from ingest.nirf_programme import read

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
ROUTES = ROOT / "backend" / "snapshot" / "exam_routes.json"
RAW_NIRF = {"clat": ROOT / "data" / "raw" / "nirf_law", "neet-ug": ROOT / "data" / "raw" / "nirf_medical"}
PROGRAMME = {
    "clat": ("ug[5years", "UG [5 Years Program(s)]: Placement", "5-year integrated law degrees"),
    "neet-ug": ("ug[5years", "UG [5 Years Program(s)]: Placement", "5-year undergraduate degrees (MBBS or BDS)"),
}
OUTCOME_NOTE = {
    "clat": "Self-reported by the university to NIRF, and not audited. Covers all its 5-year law degree students, not one course.",
    "neet-ug": "Self-reported to NIRF, and not audited. NIRF doesn't define what counts as placed for doctors, so read it as the college reports it. Higher studies usually means a postgraduate seat.",
}
MIN_ALUMNI = 30
ALUMNI_CAVEAT = ("A small, public sample of notable people on Wikidata, not the alumni network. It leans towards academics and "
                 "public figures, records no degree or year, and says little about typical graduates.")
FACULTY_NOTE = "Whole university, self-reported to NIRF. A count of people, which doesn't show how well anyone teaches."


def key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def manifest(folder: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in (folder / "manifest.jsonl").read_text().splitlines() if line.strip()]
    return {Path(r["slug"]).stem: r for r in rows}


def institutes_matching(route: dict, match: str) -> list[str]:
    found = sorted({r["institute"] for r in route["records"] if r["institute"].startswith(match)})
    if not found:
        raise SystemExit(f"{route['code']}: '{match}' matches no institute")
    return found


def nirf_profile(route_code: str, entry: dict, files: dict[str, dict]) -> dict:
    folder = RAW_NIRF[route_code]
    path = folder / entry["file"]
    title_mark, heading, label = PROGRAMME[route_code]
    document = read(path, title_mark, heading)
    if key(document.institute_name or "") != key(entry["printed_name"]):
        raise SystemExit(f"{entry['file']} prints {document.institute_name!r}, not {entry['printed_name']!r}")
    source = files[path.stem]
    excluded = entry.get("exclude") or {}
    years = [asdict(y) for y in document.years if y.academic_year not in excluded]
    academics = read_document(path)
    faculty = asdict(academics["faculty"])
    research = {year: values for year, values in sorted(academics["years"].items()) if any(v is not None for v in values.values())}
    title = f"NIRF {document.nirf_year or ''} {document.category or ''} submission, as published by the university".replace("  ", " ")
    common = {"source_title": title, "source_url": source["url"], "retrieved": source["retrieved"][:10], "nirf_id": document.institute_code}
    return {
        "outcomes": {
            "programme": label, "years": years, "excluded": [{"academic_year": y, "reason": r} for y, r in excluded.items()],
            "note": OUTCOME_NOTE[route_code], "year_note": entry.get("year_note"), "status": "official", **common,
        } if years else None,
        "faculty": {
            "regular": faculty["regular"], "with_phd": faculty["with_phd"], "listed": faculty["listed"], "current": faculty["current"],
            "professors": faculty["professors"], "associate": faculty["associate"], "assistant": faculty["assistant"],
            "median_experience_years": round(faculty["median_experience_months"] / 12, 1) if faculty.get("median_experience_months") else None,
            "students_total": academics["students_total"], "phd_students": academics["phd_students"],
            "students_per_regular_faculty": round(academics["students_total"] / faculty["regular"], 1) if academics["students_total"] and faculty["regular"] else None,
            "research_years": research, "problems": academics["problems"] + faculty["problems"], "note": FACULTY_NOTE, "status": "official", **common,
        } if faculty.get("regular") else None,
    }


def build(data: dict) -> dict[str, dict[str, int]]:
    websites = yaml.safe_load((REGISTRY / "exam_institute_websites.yaml").read_text())
    fees = yaml.safe_load((REGISTRY / "exam_fees.yaml").read_text())
    nirf = yaml.safe_load((REGISTRY / "exam_nirf_documents.yaml").read_text())
    routes = {r["code"]: r for r in data["routes"]}
    profiles: dict[str, dict[str, dict]] = {}
    counts: dict[str, dict[str, int]] = {}

    def put(code: str, match: str, field: str, value: dict | None) -> None:
        if value is None:
            return
        for institute in institutes_matching(routes[code], match):
            profiles.setdefault(code, {}).setdefault(institute, {})[field] = value
            counts.setdefault(code, {}).setdefault(field, 0)
            counts[code][field] += 1

    for code, entries in websites["websites"].items():
        for e in entries:
            source = websites["sources"][e["source"]]
            put(code, e["match"], "website", {"url": e["url"], "note": e.get("note"), "source_title": source["title"], "source_url": source["url"], "status": source["status"]})
    for code, entries in fees["fees"].items():
        for e in entries:
            put(code, e["match"], "fee", {
                "title": e["title"], "note": e.get("note") or "As printed in the university's own fee notice.", "declared": e["declared"],
                "source_url": e["url"], "year": fees["year"], "status": "official",
            })
    for code, entries in nirf["documents"].items():
        files = manifest(RAW_NIRF[code])
        for e in entries:
            profile = nirf_profile(code, e, files)
            put(code, e["match"], "outcomes", profile["outcomes"])
            put(code, e["match"], "faculty", profile["faculty"])
    # Other NIRF lists, joined on the institution number shared across NIRF's lists.
    other = yaml.safe_load((REGISTRY / "nirf_2025_other_lists.yaml").read_text())
    by_number: dict[str, list[dict]] = {}
    for category, listing in other["lists"].items():
        for row in listing["ranks"]:
            by_number.setdefault(row["nirf_id"].split("-", 2)[2], []).append({
                "category": category, "rank": row["rank"], "year": other["year"], "name": row["name"], "source_url": listing["source"], "status": "official",
                "note": "Covers the whole university, not one college or course.",
            })
    primary = yaml.safe_load((REGISTRY / "nirf_2025_exam_routes.yaml").read_text())
    ids = {(category, e["name"]): e["nirf_id"] for category, listing in primary["lists"].items() for e in listing["ranks"]}
    for code, route in routes.items():
        seen: set[str] = set()
        for record in route["records"]:
            ranking = record.get("ranking") or {}
            number = ids.get((ranking.get("category"), ranking.get("name")), "").split("-", 2)[-1]
            if record["institute"] in seen or number not in by_number:
                continue
            seen.add(record["institute"])
            profiles.setdefault(code, {}).setdefault(record["institute"], {})["other_rankings"] = by_number[number]
            counts.setdefault(code, {}).setdefault("other_rankings", 0)
            counts[code]["other_rankings"] += 1
    # Alumni samples from Wikidata: exam_alumni.json for law and medical colleges, and the JEE counts for GATE
    # institutes whose name exactly matches a JoSAA institute. Samples under 30 people aren't shown, as for JEE.
    alumni_file = ROOT / "data" / "import" / "exam_alumni.json"
    samples = [s for s in json.loads(alumni_file.read_text())] if alumni_file.exists() else []
    institutions = yaml.safe_load((REGISTRY / "institutions.yaml").read_text())
    slugs: dict[str, set[str]] = {}
    for inst in institutions:
        for name in [*inst["names"], inst["short"]]:
            slugs.setdefault(key(name), set()).add(inst["slug"])
    for institute in sorted({r["institute"] for r in routes["gate-ccmt"]["records"]}):
        found = slugs.get(key(institute), set())
        cache = ROOT / "data" / "raw" / "wikidata" / f"{next(iter(found))}.json" if len(found) == 1 else None
        if cache and cache.exists():
            samples.append({"route": "gate-ccmt", "match": institute, **json.loads(cache.read_text())})
    for sample in samples:
        if (sample.get("sample_size") or 0) < MIN_ALUMNI:
            continue
        put(sample["route"], sample["match"], "alumni", {
            "sample_size": sample["sample_size"], "founders": sample.get("founders"),
            "occupations": [{"label": o["label"], "people": o["count"]} for o in sample["occupation"]],
            "employers": [{"label": o["label"], "people": o["count"]} for o in sample["employer"]],
            "caveat": ALUMNI_CAVEAT, "source_title": f"Wikidata, people listing this institute as where they studied ({sample['qid']})",
            "source_url": f"https://www.wikidata.org/wiki/{sample['qid']}", "retrieved": sample["retrieved_at"][:10], "status": "secondary",
        })
    data["profiles"] = profiles
    return counts


def main() -> None:
    data = json.loads(ROUTES.read_text())
    counts = build(data)
    ROUTES.write_text(json.dumps(data, ensure_ascii=False))
    for code, fields in counts.items():
        print(code, fields)


if __name__ == "__main__":
    main()
