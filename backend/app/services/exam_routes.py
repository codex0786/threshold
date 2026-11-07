"""Admission routes beyond JEE. Shows past figures only, with no bands or probabilities.

Reads backend/snapshot/exam_routes.json, which like the JEE snapshot is git-ignored and bundled at deploy time.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MAX_PROGRAMME_CHOICES = 6
DATA = Path(__file__).resolve().parents[2] / "snapshot" / "exam_routes.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(DATA.read_text()) if DATA.exists() else {"routes": []}


def summary(route: dict) -> dict:
    records = route["records"]
    return {
        **{k: v for k, v in route.items() if k != "records"},
        "record_count": len(records),
        "institute_count": len({r["institute"] for r in records}),
        "categories": sorted({r["category"] for r in records}),
        "groups": sorted({r["group"] for r in records if r.get("group")}),
        "programmes": sorted({r["programme"] for r in records}) if len({r["programme"] for r in records}) <= MAX_PROGRAMME_CHOICES else [],
    }


def within(route: dict, record: dict, value: float) -> bool:
    """Whether a past closing figure is at or beyond the student's own figure on the same scale."""
    if route["metric"]["lower_is_better"]:
        return record["value"] >= value
    return record["value"] <= value


def invalid_value(route: dict, value: float) -> str | None:
    """Why a figure can't exist on this route's scale, if it can't."""
    metric = route["metric"]
    if metric.get("whole_number") and value != int(value):
        return f"{metric['label']} must be a whole number."
    if metric.get("max") is not None and value > metric["max"]:
        return f"{metric['label']} can't be above {metric['max']}."
    return None


def query(route: dict, value: float | None = None, category: str | None = None, group: str | None = None, search: str | None = None, limit: int = 50, programme: str | None = None) -> dict:
    needle = (search or "").casefold()
    lower_is_better = route["metric"]["lower_is_better"]
    records = [
        r for r in route["records"]
        if (not category or r["category"] == category) and (not group or r.get("group") == group) and (not programme or r["programme"] == programme)
        and (not needle or needle in r["institute"].casefold() or needle in r["programme"].casefold())
    ]
    no_figure = [r for r in records if r["value"] is None]
    usable = [r for r in records if r["value"] is not None]
    # Categories have separate cut-offs and some quotas have their own eligibility, so a student's figure is never compared across them.
    missing = [] if category else ["category"]
    if route.get("compare_requires_group") and not group:
        missing.append("quota")
    compared = value is not None and not missing
    matched = [r for r in usable if within(route, r, value)] if compared else usable
    # Strongest past outcomes first.
    matched.sort(key=lambda r: (r["value"] if lower_is_better else -r["value"], r["institute"], r["programme"]))
    return {"total": len(usable), "matched": len(matched), "compared": compared, "missing": missing, "no_figure": no_figure[:limit], "records": matched[:limit]}
