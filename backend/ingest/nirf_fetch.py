"""Download NIRF submissions from institute websites and write a reviewable CSV.

Usage: python -m ingest.nirf_fetch
Nothing reaches the database here. The CSV goes through ingest.import_records.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

from ingest.nirf_pdf import Extraction, extract

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "nirf"
OUTPUT = ROOT / "data" / "import" / "placements_nirf.csv"
REPORT = ROOT / "data" / "import" / "placements_nirf_report.json"
# An Overall submission can include non-engineering programmes, so its figures may differ.
DEFINITION_BY_CATEGORY = {"Engineering": "nirf_graduation_outcomes", "Overall": "nirf_graduation_outcomes_overall"}
USER_AGENT = "Mozilla/5.0 Threshold-data-ingest/0.1 (education research; low-volume)"
FIELDS = [
    "source_key",
    "institution_slug", "programme_id", "scope", "cohort_label", "reporting_definition", "graduation_year", "total_students",
    "eligible_students", "graduating_students", "students_placed", "higher_studies_students", "total_offers", "median_salary_inr",
    "average_salary_inr", "highest_domestic_salary_inr", "verification_status", "source_title", "source_url", "source_file", "source_page", "reporting_year", "notes",
]


def download(url: str, path: Path, attempts: int = 2) -> bool:
    if path.exists():
        return True
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        except requests.RequestException as error:
            print(f"  {url}: {type(error).__name__}")
            time.sleep(3)
            continue
        time.sleep(1.5)
        if response.status_code == 200 and response.content.startswith(b"%PDF"):
            path.write_bytes(response.content)
            return True
        print(f"  {url}: HTTP {response.status_code}, not a PDF")
        return False
    return False


def normalise(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def name_matches(document_name: str | None, slug: str, known_names: dict[str, list[str]], overrides: dict[str, list[str]]) -> bool:
    """Exact or containment only. Fuzzy matching would treat NIT Goa and NIT Patna as the same."""
    if not document_name:
        return False
    doc = normalise(document_name)
    if doc in (normalise(n) for n in overrides.get(slug, [])):
        return True
    for known in known_names[slug]:
        name = normalise(known)
        if doc == name or (len(doc) >= 25 and (doc in name or name in doc)):
            return True
    return False


def check_document(result: Extraction, slug: str, listed_year: int, names: dict, overrides: dict, reviewed: dict | None = None) -> list[str]:
    cleared = (reviewed or {}).get(slug, {})
    problems = [p for p in result.problems if not ("disagree" in p and any(f", {year}:" in p for year in cleared))]
    if not name_matches(result.institute_name, slug, names, overrides):
        problems.append(f"Institute name in the document ({result.institute_name}) doesn't match {slug}")
    if result.nirf_year != listed_year:
        problems.append(f"Document year {result.nirf_year} differs from the listed year {listed_year}")
    if result.category not in ("Engineering", "Overall"):
        problems.append(f"Category {result.category} isn't Engineering or Overall")
    if not result.rows:
        problems.append("No outcome rows")
    return problems


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    registry = yaml.safe_load((ROOT / "data" / "registry" / "nirf_documents.yaml").read_text())
    institutions = yaml.safe_load((ROOT / "data" / "registry" / "institutions.yaml").read_text())
    names = {i["slug"]: i["names"] for i in institutions}
    overrides = yaml.safe_load((ROOT / "data" / "registry" / "nirf_name_overrides.yaml").read_text()) or {}
    reviewed = yaml.safe_load((ROOT / "data" / "registry" / "nirf_reviewed_discrepancies.yaml").read_text()) or {}
    rows, report = [], {}
    for slug, candidates in registry.items():
        entry: dict = {"status": "no_document", "problems": []}
        for candidate in candidates:
            path = RAW / f"{slug}_{candidate['year']}_{hashlib.sha256(candidate['url'].encode()).hexdigest()[:8]}.pdf"
            if not download(candidate["url"], path):
                continue
            result = extract(path)
            problems = check_document(result, slug, candidate["year"], names, overrides, reviewed)
            entry = {
                "status": "needs_review" if problems else "extracted",
                "url": candidate["url"], "file": path.name, "document_institute": result.institute_name, "document_code": result.institute_code,
                "document_year": result.nirf_year, "category": result.category, "problems": problems, "rows": len(result.rows),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            if problems:
                continue
            for row in result.rows:
                if row.median_salary_inr is None and row.students_placed is None:
                    continue
                rows.append({
                    "source_key": "nirf_institute_submissions", "institution_slug": slug, "programme_id": "", "scope": "institution", "cohort_label": "All 4-year UG programmes",
                    "reporting_definition": DEFINITION_BY_CATEGORY[result.category], "graduation_year": row.graduation_year,
                    "graduating_students": row.graduating_students or "", "students_placed": row.students_placed if row.students_placed is not None else "",
                    "higher_studies_students": row.higher_studies_students if row.higher_studies_students is not None else "",
                    "median_salary_inr": row.median_salary_inr or "", "verification_status": "official",
                    "source_title": f"{names[slug][0]}: NIRF {result.nirf_year} submitted data ({result.category})",
                    "source_url": candidate["url"], "source_file": f"data/raw/nirf/{path.name}", "source_page": row.page, "reporting_year": result.nirf_year,
                    "notes": " ".join(filter(None, [
                        "Self-reported by the institute to NIRF. Machine-extracted and automatically cross-checked, awaiting independent review.",
                        reviewed.get(slug, {}).get(row.academic_year),
                    ])),
                })
            break
        report[slug] = entry
        print(f"{slug}: {entry['status']} {entry.get('category')} NIRF {entry.get('document_year')} rows={entry.get('rows', 0)} {entry['problems'][:3]}")
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    REPORT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "institutes": report}, indent=2))
    extracted = sum(1 for e in report.values() if e["status"] == "extracted")
    print(f"Wrote {len(rows)} rows from {extracted} institutes to {OUTPUT}")


if __name__ == "__main__":
    main()
