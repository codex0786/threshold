"""Admission routes beyond JEE. Shows past figures only, with no bands or probabilities.

Reads backend/snapshot/exam_routes.json, which like the JEE snapshot is git-ignored and bundled at deploy time.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.services.scoring import NEUTRAL, contest_scores, reputation_score

MAX_PROGRAMME_CHOICES = 8
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


def requirement(route: dict, quota: str) -> str | None:
    """What a student needs to use a quota, or None when it's open to everyone. Spacing in MCC's names varies."""
    wanted = re.sub(r"\s+", "", quota)
    return next((need for name, need in (route.get("quota_requirements") or {}).items() if re.sub(r"\s+", "", name) == wanted), None)


def group_order(route: dict):
    """Sort key that keeps each round's groups together, in the route's round order, when the route lists its rounds."""
    rounds = {label: index for index, label in enumerate(route.get("rounds") or [])}
    return lambda g: (rounds.get(g.rsplit(" · ", 1)[-1], len(rounds)), g) if " · " in g else (len(rounds), g)


def summary(route: dict) -> dict:
    records = route["records"]
    key = group_order(route)
    return {
        **{k: v for k, v in route.items() if k != "records"},
        "record_count": len(records),
        "institute_count": len({r["institute"] for r in records}),
        "categories": sorted({r["category"] for r in records}),
        "groups": sorted(combined_groups(route), key=key) + sorted({r["group"] for r in records if r.get("group")}, key=key),
        "group_requirements": {g: need for g in {r["group"] for r in records if r.get("group")} if (need := requirement(route, g.rsplit(" · ", 1)[0]))},
        "ranked_institute_count": len({r["institute"] for r in records if r.get("ranking")}),
        "fee_institute_count": len({r["institute"] for r in records if r.get("fee")}),
        "quotas": quotas(route),
        "quota_requirements": {q: need for q in quotas(route) if (need := requirement(route, q))},
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
    limit: int = 50, programme: str | None = None, order: str = "top", gender: str | None = None, eligible: frozenset[str] = frozenset(),
) -> dict:
    needle = (search or "").casefold()
    lower_is_better = route["metric"]["lower_is_better"]
    in_group = combined_groups(route).get(group or "", {group})
    eligible_for = eligible
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
        # Suggest lists from the round the student is looking at, so rounds aren't mixed.
        same_round = group.rsplit(" · ", 1)[1] if " · " in group else None
        for r in eligible:
            need = requirement(route, r.get("group", "").rsplit(" · ", 1)[0])
            if (
                (need is None or need in eligible_for) and (same_round is None or r.get("group", "").endswith(f" · {same_round}"))
                and r["category"] == category and r.get("group") not in in_group and r["value"] is not None and within(route, r, value)
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


# Shortlist. Every route covers one year, and one year can't support the JEE bands, which need two or more
# (see app/services/bands.py). So a seat is placed by the round of that year in which it first reached the
# student, which is a fact about one year, not a forecast.
POSITIONS = {
    "first_round": ("Reached your {unit} in the first round", "In the first round, this seat's last allotment was at or beyond your {unit}."),
    "later_round": ("Reached your {unit} in a later main round", "It reached your {unit} only after the first round, as seats were given up and filled again."),
    "leftover_round": ("Only in a stray, special or spot round", "It reached your {unit} only in a round for seats still empty near the end. Check who may take part in that round before relying on it."),
    "reached": ("Reached your {unit}", "The published cut-off was at or beyond your {unit}."),
    "near": ("Just beyond your {unit}", "It never reached your {unit} that year, but its furthest figure was within 20% of it."),
}
NEAR_MARGIN = 1.20
LEFTOVER = re.compile(r"stray|special|spot", re.I)
POSITION_LIMIT = 100
OUTCOMES = {
    "Medical": "Graduate outcomes, such as postgraduate seats or jobs, aren't collected for this course.",
    "Law": "Placement figures aren't collected for law schools yet.",
    "Engineering": "Placement figures for this course aren't collected yet.",
}


def base_quota(group: str | None) -> str | None:
    return group.rsplit(" · ", 1)[0] if group and " · " in group else group


def round_of(group: str | None) -> str | None:
    return group.rsplit(" · ", 1)[1] if group and " · " in group else None


def quotas(route: dict) -> list[str]:
    """Quotas a student chooses from, without the round. Joined quotas come first."""
    bases = {base_quota(r.get("group")) for r in route["records"] if r.get("group")}
    joined = [name for name, members in (route.get("combined_quotas") or {}).items() if len(set(members) & bases) > 1]
    return joined + sorted(bases)


def lower_first(label: str) -> str:
    """Lowercases a label's first letter for use mid-sentence, unless it starts an acronym such as AIR."""
    return label[0].lower() + label[1:] if len(label) > 1 and label[1].islower() else label


def fmt(route: dict, value: float) -> str:
    return f"{value:,.0f}" if route["metric"].get("whole_number") or value == int(value) else str(value)


def _seat(route: dict, rows: list[dict], value: float) -> dict | None:
    metric, rounds = route["metric"], route.get("rounds") or []
    unit, lower = metric["unit"], metric["lower_is_better"]
    index = {label: i for i, label in enumerate(rounds)}
    rows = sorted(rows, key=lambda r: index.get(round_of(r.get("group")), len(rounds)))
    ladder = [
        {"round": round_of(r.get("group")), "value": r["value"], "second_value": r.get("second_value"), "count": r.get("count"),
         "reached": r["value"] is not None and within(route, r, value)}
        for r in rows
    ]
    figures = [step for step in ladder if step["value"] is not None]
    if not figures:
        return None
    furthest = (max if lower else min)(step["value"] for step in figures)
    first = next((step for step in ladder if step["reached"]), None)
    why = []
    if first is None:
        if not lower or furthest * NEAR_MARGIN < value:
            return None
        position = "near"
        where = next(step["round"] for step in figures if step["value"] == furthest)
        why.append(f"Its furthest {lower_first(metric['value_label'])} was {fmt(route, furthest)}{f' in {where}' if where else ''}, and yours is {fmt(route, value)}.")
    elif not rounds:
        position = "reached"
        why.append(f"{metric['value_label']}: {fmt(route, first['value'])}. Yours is {fmt(route, value)}.")
    else:
        position = "first_round" if first["round"] == rounds[0] else "leftover_round" if LEFTOVER.search(first["round"] or "") else "later_round"
        why.append(f"In {first['round']}, the {lower_first(metric['value_label'])} was {fmt(route, first['value'])}. Yours is {fmt(route, value)}.")
        if position == "later_round":
            earlier = [step for step in ladder if step["value"] is not None and index.get(step["round"], 0) < index.get(first["round"], 0)]
            if earlier:
                why.append(f"Earlier, in {earlier[-1]['round']}, it stopped at {fmt(route, earlier[-1]['value'])}.")
            elif index.get(first["round"], 0) > 0:
                why.append(f"This seat has no figure for the rounds before {first['round']}.")
    missed = [step["round"] for step in ladder if first is not None and step["value"] is not None and not step["reached"]
              and index.get(step["round"], 0) > index.get(first["round"], 0) and not LEFTOVER.search(step["round"] or "")]
    if missed:
        why.append(f"It didn't reach your {unit} in {', '.join(missed)}.")
    if rounds and "provisional" in (ladder[0]["round"] or "") and position == "first_round":
        why.append(f"{ladder[0]['round']} figures were published as provisional.")
    if not lower:
        why.append(f"A higher {unit} is better on this exam.")
    last = rows[-1]
    with_fee = next((r["fee"] for r in reversed(rows) if r.get("fee")), None)
    ranking = next((r["ranking"] for r in rows if r.get("ranking")), None)
    return {
        "institute": last["institute"], "institute_short": last.get("institute_short"), "programme": last["programme"],
        "programme_code": last.get("programme_code"), "quota": base_quota(last.get("group")), "category": last["category"],
        "female_only": any(r.get("female_only") for r in rows), "seats": last.get("seats"), "note": last.get("note"),
        "position": position, "rounds": ladder, "furthest": furthest, "ranking": ranking, "fee": with_fee,
        "standing": max(r.get("standing", NEUTRAL) for r in rows), "why": why,
        "margin": abs((first or {"value": furthest})["value"] - value),
    }


def shortlist(
    route: dict, value: float | None, category: str | None, quota: str | None, programme: str | None = None,
    gender: str | None = None, order: str = "top", search: str | None = None,
) -> dict:
    """A student's seats in one route, each with every round of the year in which it was allotted."""
    missing = [name for name, given in (("figure", value is not None), ("category", bool(category))) if not given]
    if route.get("compare_requires_group") and not quota:
        missing.append("quota")
    unit = route["metric"]["unit"]
    labels = {key: {"label": label.format(unit=unit), "hint": hint.format(unit=unit)} for key, (label, hint) in POSITIONS.items()}
    if missing:
        return {"missing": missing, "positions": labels, "counts": {}, "options": [], "beyond": 0, "hidden_female_only": 0}
    members = set((route.get("combined_quotas") or {}).get(quota or "", [quota])) if quota else None
    needle = (search or "").casefold()
    seats: dict[tuple, list[dict]] = defaultdict(list)
    hidden = 0
    for r in route["records"]:
        if r["category"] != category or (members and base_quota(r.get("group")) not in members) or (programme and r["programme"] != programme):
            continue
        if needle and needle not in r["institute"].casefold() and needle not in r["programme"].casefold():
            continue
        if gender in ("male", "other") and r.get("female_only"):
            hidden += 1
            continue
        seats[(r["institute"], r.get("programme_code") or r["programme"], base_quota(r.get("group")))].append(r)
    options, beyond = [], 0
    for rows in seats.values():
        seat = _seat(route, rows, value)
        if seat is None:
            beyond += 1
        else:
            options.append(seat)
    if order == "closest":
        options.sort(key=lambda o: (o["margin"], o["institute"], o["programme"]))
    else:
        options.sort(key=lambda o: (-o["standing"], o["margin"], o["institute"], o["programme"]))
    counts: dict[str, int] = defaultdict(int)
    shown = []
    for option in options:
        counts[option["position"]] += 1
        if counts[option["position"]] <= POSITION_LIMIT:
            shown.append(option)
    gaps = [OUTCOMES.get(route["stream"], OUTCOMES["Engineering"])]
    return {
        "missing": [], "positions": labels, "counts": dict(counts), "options": shown, "beyond": beyond, "hidden_female_only": hidden,
        "limit": POSITION_LIMIT, "route_gaps": gaps,
    }
