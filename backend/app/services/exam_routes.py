"""Admission routes beyond JEE. Shows past figures only, with no bands or probabilities.

Reads backend/snapshot/exam_routes.json, which like the JEE snapshot is git-ignored and bundled at deploy time.
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.services.scoring import NEUTRAL, contest_scores, reputation_score

MAX_PROGRAMME_CHOICES = 6
DATA = Path(__file__).resolve().parents[2] / "snapshot" / "exam_routes.json"


def add_standing(route: dict) -> None:
    """Default list position, as on the JEE shortlist: two parts NIRF rank to one part how contested the seat is.

    NIRF rank uses the reputation scale (rank 1 is 100, rank 100 is 50.5) and a missing rank counts as a
    neutral 50. How contested a seat is compares its closing figure only with the same course, category and
    list, so it never mixes rank lists. It only orders the list. It isn't a quality score.
    """
    lower_is_better = route["metric"]["lower_is_better"]
    # Quotas shown together are scored together, or AIIMS seats would only be compared with other AIIMS seats.
    together = {member: name for name, members in combined_groups(route).items() for member in members}
    peers: dict[tuple, dict[int, float]] = defaultdict(dict)
    for index, record in enumerate(route["records"]):
        if record["value"] is not None:
            group = together.get(record.get("group"), record.get("group"))
            peers[(record["programme"], record["category"], group)][index] = record["value"] if lower_is_better else -record["value"]
    contest = {index: score for group in peers.values() for index, score in contest_scores(group).items()}
    for index, record in enumerate(route["records"]):
        institute = reputation_score((record.get("ranking") or {}).get("rank"))
        record["standing"] = round((2 * (NEUTRAL if institute is None else institute) + contest.get(index, NEUTRAL)) / 3, 1)


@lru_cache(maxsize=1)
def load() -> dict:
    data = json.loads(DATA.read_text()) if DATA.exists() else {"routes": []}
    for route in data["routes"]:
        add_standing(route)
    return data


def combined_groups(route: dict) -> dict[str, set[str]]:
    """Lists that join quotas open to the same candidates, such as MCC's All India and Open Seat Quota (AIIMS,
    JIPMER), one per round. Returns each combined name with the published groups it covers."""
    groups = {r["group"] for r in route["records"] if r.get("group")}
    combined: dict[str, set[str]] = {}
    for name, quotas in (route.get("combined_quotas") or {}).items():
        for round_label in sorted({g.rsplit(" · ", 1)[1] for g in groups if " · " in g}):
            members = {f"{quota} · {round_label}" for quota in quotas} & groups
            if len(members) > 1:
                combined[f"{name} · {round_label}"] = members
    return combined


def summary(route: dict) -> dict:
    records = route["records"]
    return {
        **{k: v for k, v in route.items() if k != "records"},
        "record_count": len(records),
        "institute_count": len({r["institute"] for r in records}),
        "categories": sorted({r["category"] for r in records}),
        "groups": sorted(combined_groups(route)) + sorted({r["group"] for r in records if r.get("group")}),
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


def query(
    route: dict, value: float | None = None, category: str | None = None, group: str | None = None, search: str | None = None,
    limit: int = 50, programme: str | None = None, order: str = "top", gender: str | None = None,
) -> dict:
    needle = (search or "").casefold()
    lower_is_better = route["metric"]["lower_is_better"]
    in_group = combined_groups(route).get(group or "", {group})
    # Seats only women may hold are hidden once a student says they're male or other, and labelled until then.
    eligible = [r for r in route["records"] if not (gender in ("male", "other") and r.get("female_only"))]
    hidden_female_only = len(route["records"]) - len(eligible)
    records = [
        r for r in eligible
        if (not category or r["category"] == category) and (not group or r.get("group") in in_group) and (not programme or r["programme"] == programme)
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
    closest = (lambda r: r["value"]) if lower_is_better else (lambda r: -r["value"])
    if order == "top":
        matched.sort(key=lambda r: (-r.get("standing", NEUTRAL), closest(r), r["institute"], r["programme"]))
    else:
        matched.sort(key=lambda r: (closest(r), r["institute"], r["programme"]))
    # When nothing in the chosen list reaches the student, say how far it went and which other quotas did.
    furthest = (max if lower_is_better else min)((r["value"] for r in usable), default=None)
    elsewhere: dict[str, int] = {}
    if compared and route.get("compare_requires_group"):
        for r in eligible:
            if (
                r["category"] == category and r.get("group") not in in_group and r["value"] is not None and within(route, r, value)
                and (not programme or r["programme"] == programme)
                and (not needle or needle in r["institute"].casefold() or needle in r["programme"].casefold())
            ):
                elsewhere[r["group"]] = elsewhere.get(r["group"], 0) + 1
    return {
        "total": len(usable), "matched": len(matched), "compared": compared, "missing": missing, "furthest": furthest,
        "hidden_female_only": hidden_female_only,
        "elsewhere": [{"group": g, "count": n} for g, n in sorted(elsewhere.items(), key=lambda item: -item[1])],
        "no_figure": no_figure[:limit], "records": matched[:limit],
    }
