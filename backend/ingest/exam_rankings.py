"""Attach official NIRF ranks to the routes beyond JEE, from data/registry/nirf_2025_exam_routes.yaml.

Rewrites backend/snapshot/exam_routes.json in place. Stops if any listed match finds no institute, so a
renamed or mistyped entry can't silently drop a rank.

Usage: python -m ingest.exam_rankings
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry" / "nirf_2025_exam_routes.yaml"
ROUTES = ROOT / "backend" / "snapshot" / "exam_routes.json"


def attach(data: dict, registry: dict) -> dict[str, int]:
    """Set `ranking` on each record whose institute and programme a list covers. Returns matches per list."""
    matched: dict[str, int] = {}
    found: set[tuple[str, str]] = set()
    for route in data["routes"]:
        for record in route["records"]:
            record.pop("ranking", None)
        for category in registry["routes"].get(route["code"], []):
            listing = registry["lists"][category]
            programmes = set(listing.get("programmes") or [])
            for entry in listing["ranks"]:
                hits = [
                    r for r in route["records"]
                    if r["institute"].startswith(entry["match"]) and (not programmes or r["programme"] in programmes)
                ]
                for record in hits:
                    record["ranking"] = {
                        "category": category, "rank": entry["rank"], "year": registry["year"],
                        "name": entry["name"], "source_url": listing["source"], "status": "official",
                    }
                if hits:
                    found.add((category, entry["match"]))
                    matched[f"{route['code']} {category}"] = matched.get(f"{route['code']} {category}", 0) + 1
    # Every entry must match somewhere. A list can serve several routes, so it needn't match in each one.
    for category, listing in registry["lists"].items():
        for entry in listing["ranks"]:
            if (category, entry["match"]) not in found:
                raise SystemExit(f"No institute starts with {entry['match']!r} ({category})")
    return matched


if __name__ == "__main__":
    data = json.loads(ROUTES.read_text())
    for name, count in attach(data, yaml.safe_load(REGISTRY.read_text())).items():
        print(f"{name}: {count} institutes ranked")
    ROUTES.write_text(json.dumps(data))
