"""Help with the decision after each JoSAA round: Freeze, Float or Slide.

JoSAA's options after an allotment:
- Freeze: accept this seat and leave later rounds.
- Float: keep this seat, but take any higher choice on your list if one opens up.
- Slide: keep this seat, but take a higher choice only at the same institute.

We look at each choice above the allotted one and check, for recent years, whether the same seat
(same quota, seat type and pool) ended up closing at or beyond the student's rank by the final round.
That is past behaviour of seats, not a forecast for this year, and the advice says so.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CutoffRecord
from app.schemas import StudentProfile
from app.services import preferences
from app.services.bands import LOOKBACK_YEARS

OPTIONS = {
    "freeze": "Freeze: accept this seat and leave the later rounds.",
    "float": "Float: keep this seat, and move up to any higher choice on your list that opens in a later round.",
    "slide": "Slide: keep this seat, and move up only to a higher choice at the same institute.",
}


def _history(db: Session, programme_id: int, route: dict, data_year: int) -> dict[int, dict[str, int | None]]:
    """Closing ranks by year: the earliest round we hold, each round, and the final round."""
    rows = db.scalars(select(CutoffRecord).where(
        CutoffRecord.programme_id == programme_id, CutoffRecord.quota == route["quota"], CutoffRecord.seat_type == route["seat_type"],
        CutoffRecord.gender_pool == route["gender_pool"], CutoffRecord.rank_list == route["rank_list"], CutoffRecord.is_preparatory.is_(False),
        CutoffRecord.closing_rank.is_not(None), CutoffRecord.year > data_year - LOOKBACK_YEARS,
    ))
    by_year: dict[int, dict] = defaultdict(lambda: {"rounds": {}, "final": None})
    for r in rows:
        by_year[r.year]["rounds"][r.round] = r.closing_rank
        if r.is_final_round:
            by_year[r.year]["final"] = r.closing_rank
    return by_year


def _round_closing(rounds: dict[int, int], round_no: int) -> tuple[int | None, int | None]:
    """The closing rank at this round, or the latest earlier round we hold."""
    held = [r for r in rounds if r <= round_no]
    if not held:
        return None, None
    used = max(held)
    return rounds[used], used


def advise(db: Session, profile: StudentProfile, programme_ids: list[int], allotted_programme_id: int, round_no: int, final_round: int = 5) -> dict:
    if allotted_programme_id not in programme_ids:
        raise ValueError("The allotted programme must be on the list")
    analysis = preferences.analyse(db, profile, programme_ids)
    data_year = analysis["data_year"]
    items = analysis["items"]
    allotted_index = programme_ids.index(allotted_programme_id)
    allotted = items[allotted_index]
    higher = items[:allotted_index]

    checked = []
    for item in higher:
        route = item["routes"][0] if item.get("routes") else None
        entry = {
            "position": item["position"], "programme_id": item["programme_id"], "programme": item.get("programme"),
            "institution": item["institution"]["short_name"], "same_institute": item["institution"]["slug"] == allotted["institution"]["slug"],
            "band": item.get("band"), "years": [], "reached_years": 0, "opened_later_years": 0, "status": "no_history",
        }
        if route:
            history = _history(db, item["programme_id"], route, data_year)
            for year in sorted(history):
                h = history[year]
                at_round, used = _round_closing(h["rounds"], round_no)
                final = h["final"]
                reached = final is not None and route["rank_used"] <= final
                opened_later = reached and at_round is not None and route["rank_used"] > at_round
                entry["years"].append({"year": year, "closing_at_round": at_round, "round_used": used, "final_closing": final, "reached_by_final": reached})
                entry["reached_years"] += int(reached)
                entry["opened_later_years"] += int(opened_later)
            years_with_final = sum(1 for y in entry["years"] if y["final_closing"] is not None)
            if years_with_final:
                share = entry["reached_years"] / years_with_final
                entry["status"] = "often" if share >= 0.67 else "sometimes" if share > 0 else "not_seen"
            entry["rank_used"] = route["rank_used"]
            entry["route"] = {k: route[k] for k in ("seat_type", "quota", "gender_pool")}
        checked.append(entry)

    hopeful = [c for c in checked if c["status"] in ("often", "sometimes")]
    hopeful_other = [c for c in hopeful if not c["same_institute"]]
    hopeful_same = [c for c in hopeful if c["same_institute"]]
    last_round = round_no >= final_round

    if not higher:
        suggestion, why = "freeze", "This is your first choice, so no later round can give you anything higher."
    elif last_round:
        suggestion, why = "freeze", "This is the last JoSAA round, so there are no later rounds to move up in. Check the JoSAA notice for what Float and Slide mean in the final round."
    elif hopeful_other:
        suggestion = "float"
        why = f"{len(hopeful_other)} higher choice{'s' if len(hopeful_other) != 1 else ''} at other institutes reached ranks like yours by the final round in recent years. Float keeps this seat and lets you move up if that happens again."
    elif hopeful_same:
        suggestion = "slide"
        why = f"The only higher choices that reached ranks like yours by the final round are at {allotted['institution']['short_name']}. Slide keeps this seat and lets you move up within it."
    else:
        suggestion = "freeze"
        why = "None of your higher choices reached ranks like yours by the final round in recent years. Freezing ends the process with this seat. Float only if you'd rather wait on a small chance."

    return {
        "round": round_no, "final_round": final_round, "data_year": data_year,
        "allotted": {"programme_id": allotted["programme_id"], "programme": allotted.get("programme"), "institution": allotted["institution"]["short_name"], "position": allotted["position"]},
        "higher_choices": checked, "suggestion": suggestion, "why": why, "options": OPTIONS,
        "cautions": [
            "This looks at how the same seats moved in past years. This year's movement depends on other candidates' choices and can be different.",
            "If you are happy with this seat, Freeze is always reasonable. Moving up is only worth it if you prefer the higher choice.",
            "You must report and pay the seat acceptance fee by JoSAA's deadline whichever option you choose, or you lose the seat. Check the current JoSAA business rules.",
            "We hold the first and final rounds for past years. Where a middle round is missing, the closing rank shown is from the latest earlier round we have.",
        ],
    }
