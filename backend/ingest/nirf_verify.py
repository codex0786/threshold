"""Read every candidate document and add the best verified one per institute to the registry.

Usage: python -m ingest.nirf_verify
Newest year wins, and Engineering is preferred over Overall within a year. Documents that
fail a check are listed for review and never added.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ingest.nirf_fetch import check_document, download
from ingest.nirf_pdf import extract

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry"
STAGING = ROOT / "data" / "raw" / "nirf_candidates"


def main() -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    documents = yaml.safe_load((REGISTRY / "nirf_documents.yaml").read_text())
    names = {i["slug"]: i["names"] for i in yaml.safe_load((REGISTRY / "institutions.yaml").read_text())}
    overrides = yaml.safe_load((REGISTRY / "nirf_name_overrides.yaml").read_text()) or {}
    finds = yaml.safe_load((REGISTRY / "nirf_search_finds.yaml").read_text())
    reviewed = yaml.safe_load((REGISTRY / "nirf_reviewed_discrepancies.yaml").read_text()) or {}
    discovered = json.loads((ROOT / "data" / "import" / "nirf_candidates.json").read_text())
    urls: dict[str, set[str]] = {}
    for slug, entry in discovered.items():
        urls.setdefault(slug, set()).update(entry["pdfs"])
    for slug, links in finds.items():
        urls.setdefault(slug.removesuffix("_extra"), set()).update(links)
    review, accepted = {}, {}
    for slug in sorted(urls):
        current = documents.get(slug) or []
        if current and current[0]["category"] == "Engineering":
            continue
        valid = []
        for url in sorted(urls[slug]):
            path = STAGING / f"{slug}_{hashlib.sha256(url.encode()).hexdigest()[:10]}.pdf"
            if not download(url, path):
                continue
            result = extract(path)
            year = result.nirf_year or 0
            problems = check_document(result, slug, year, names, overrides, reviewed)
            if problems:
                review.setdefault(slug, []).append({"url": url, "year": year, "category": result.category, "name": result.institute_name, "problems": problems[:4]})
            elif year >= 2025 and (not current or result.category == "Engineering"):
                valid.append((year, result.category == "Engineering", url, result.category))
        if valid:
            year, _, url, category = max(valid, key=lambda v: v[:2])
            accepted[slug] = {"year": year, "category": category, "url": url}
            print(f"OK {slug}: NIRF {year} {category}")
    for slug, entry in accepted.items():
        known = [c for c in documents.get(slug) or [] if c["url"] != entry["url"]]
        documents[slug] = [entry, *known]
    lines = ["# NIRF submissions on institutes' own websites. Tried in order. Each document's own institute name,", "# year and category are checked on load, by ingest.nirf_fetch and ingest.nirf_verify."]
    for slug, candidates in documents.items():
        lines.append(f"{slug}:" + ("" if candidates else " []"))
        lines += [f'  - {{year: {c["year"]}, category: {c["category"]}, url: {json.dumps(c["url"])}}}' for c in candidates]
    (REGISTRY / "nirf_documents.yaml").write_text("\n".join(lines) + "\n")
    (ROOT / "data" / "import" / "nirf_review.json").write_text(json.dumps(review, indent=2))
    print(f"Accepted {len(accepted)} new institutes. {len(review)} institutes have documents needing review")


if __name__ == "__main__":
    main()
