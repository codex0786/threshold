"""Choice lists and round advice for routes beyond JEE that have several years of history.

Only NEET UG (MCC All India counselling) for now: its rules for each round are known from MCC's UG Information
Bulletin 2026, and its history keeps each seat's closing rank round by round. Advice is a description of how
the same seats moved in past years, not a forecast, as on the JoSAA round companion.
"""
from __future__ import annotations

from app.services import exam_routes

BANDED = ("safer", "competitive", "ambitious")
BULLETIN = {
    "title": "MCC UG Information Bulletin 2026 (dated 01.08.2026)",
    "url": "https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/2026/08/20260801170630.pdf",
}
# MCC's choices after an allotment, by round, in the 2026 bulletin's own terms. Checked against the bulletin
# itself (Chapter 2, pages 8 to 14, and Chapter 15, pages 46 and 47) on 22 November 2026. MCC names two
# choices, Freeze and Float; there is no Slide option in MCC counselling (Slide is a JoSAA term).
MCC_ROUNDS = {
    1: {
        "label": "Round 1",
        "options": [
            {"key": "upgrade", "name": "Float (willing to upgrade)", "text": "Keep this seat and give willingness for upgradation online. Upload your documents on the MCC portal; you don't report in person yet. Round 2 can move you to a higher choice. If no round moves you, you report to this college after Round 3."},
            {"key": "join", "name": "Freeze (no upgradation)", "text": "Report to the allotted college in person with your original documents and join. You won't be considered for higher choices in Round 2."},
            {"key": "free_exit", "name": "Free exit", "text": "Resign or don't join. Round 1 allows a free exit: your security deposit isn't forfeited and you can take part in Round 2, but you lose any claim on this seat."},
        ],
    },
    2: {
        "label": "Round 2",
        "options": [
            {"key": "upgrade", "name": "Float (willing to upgrade)", "text": "Keep this seat and give willingness for upgradation online. Round 3 is the last round that can move you to a higher choice. If it doesn't, you report to this college after Round 3."},
            {"key": "join", "name": "Freeze (no upgradation)", "text": "Report to the allotted college in person with your original documents and join."},
        ],
        "warning": "Not joining a Round 2 seat, or resigning from it, forfeits your security deposit. If you're upgraded, you lose any claim on your earlier seat.",
    },
    3: {
        "label": "Round 3",
        "options": [{"key": "join", "name": "Join", "text": "Report to the allotted college in person. Round 3 is the last upgradation, so this seat is final."}],
        "warning": "Not reporting forfeits your security deposit and removes you from later rounds. MCC doesn't allow resignation from a Round 3 seat, and after joining you can't take part in any further counselling.",
    },
    4: {
        "label": "Stray vacancy round",
        "options": [{"key": "join", "name": "Join", "text": "A stray round seat must be joined."}],
        "warning": "Not joining a stray round seat forfeits your security deposit, and you can't take part in any later round.",
    },
}


def supported(route: dict) -> bool:
    return route["code"] == "neet-ug" and bool((route.get("history") or {}).get("by_round"))


def build(route: dict, value: int, category: str, quotas: list[str], programmes: list[str] | None = None,
          gender: str | None = None, size: int = 60, safety_net: int = 5, include_ambitious: bool = True,
          past_safety_net: bool = False) -> dict:
    """A suggested choice list across the chosen quotas and courses, top colleges first, with a safety net.

    Mirrors the JoSAA builder: MCC gives the highest choice a rank reaches, so the order should be what the
    student wants most; Safer seats at the end make sure the list ends with seats that reliably reached ranks
    like theirs. It stops after the safety net, unless the student asks to keep going.
    """
    seen, candidates, limited = set(), [], 0
    for quota in quotas:
        result = exam_routes.shortlist(route, value, category, quota, None, gender, "top")
        for option in result["options"]:
            band = (option.get("history") or {}).get("band")
            if programmes and option["programme"] not in programmes:
                continue
            if band is None and option["position"] != "near":
                limited += 1
            if band not in BANDED or (not include_ambitious and band == "ambitious"):
                continue
            identity = (option["institute"], option["programme"], option["quota"])
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(option)
    candidates.sort(key=lambda o: (-o["standing"], exam_routes.BAND_ORDER.get(o["history"]["band"], 3), o["institute"]))
    safer_available = sum(1 for o in candidates if o["history"]["band"] == "safer")
    net = min(safety_net, safer_available)
    chosen, safer_in, stop = [], 0, "ran_out"
    for option in candidates:
        if not past_safety_net and net and safer_in >= net:
            stop = "safety_net_complete"
            break
        if len(chosen) >= size:
            stop = "size_reached"
            break
        if option["history"]["band"] != "safer" and size - len(chosen) <= net - safer_in:
            continue
        safer_in += option["history"]["band"] == "safer"
        chosen.append(option)
    else:
        stop = "safety_net_complete" if net and safer_in >= net and not past_safety_net else "ran_out"
    items = [{
        "position": i, "institute": o["institute"], "institute_short": o.get("institute_short"), "programme": o["programme"],
        "quota": o["quota"], "category": o["category"], "band": o["history"]["band"], "closing": o["history"]["closing"],
        "explanation": o["history"]["explanation"], "key": o["history"]["key"],
    } for i, o in enumerate(chosen, start=1)]
    notes = []
    if not items:
        notes.append("No seat in the chosen quotas and courses has a band for your rank. Try other quotas, or see where your rank reached seats on the shortlist.")
    elif stop == "safety_net_complete":
        notes.append(f"The list stops after {net} Safer seats: in past years, choices below them were rarely reached by ranks like yours. You can keep going past them.")
    if items and safer_available < safety_net:
        notes.append(f"Only {safer_available} Safer seat{'s' if safer_available != 1 else ''} matched, so the safety net is thinner than {safety_net}. Add quotas or courses to widen it.")
    if limited:
        notes.append(f"{limited} seat{'s' if limited != 1 else ''} that reached your rank in 2026 but {'have' if limited != 1 else 'has'} too little history for a band {'were' if limited != 1 else 'was'} left out (for example the Self-Financed Merit Seat quota, new in 2026). Add them by hand from the shortlist if you want them.")
    notes.append("Move anything you'd prefer higher. MCC gives you the highest choice your rank reaches, so order by what you want most.")
    notes.append("Check that you qualify for each quota (for example NRI, minority or university quotas) before keeping it on your list.")
    counts = {b: sum(1 for i in items if i["band"] == b) for b in BANDED}
    return {"items": items, "counts": counts, "stop_reason": stop, "notes": notes, "data_years": route["history"]["years"]}


def _history(route: dict, key: str, round_no: int, value: int) -> dict:
    """How one seat moved in past years: its closing rank at this round and by the end of Round 3."""
    years, reached, opened_later = [], 0, 0
    for year, ranks in sorted(route["history"]["by_round"].get(key, {}).items()):
        index = min(round_no, 3) - 1
        at_round = next((ranks[i] for i in range(index, -1, -1) if ranks[i] is not None), None)
        final = max((r for r in ranks if r is not None), default=None)
        got = final is not None and value <= final
        later = got and at_round is not None and value > at_round
        reached += got
        opened_later += later
        years.append({"year": int(year), "closing_at_round": at_round, "final_closing": final, "reached_by_round_3": got})
    status = "no_history"
    if years:
        share = reached / len(years)
        status = "often" if share >= 0.67 else "sometimes" if share > 0 else "not_seen"
    return {"years": years, "reached_years": reached, "opened_later_years": opened_later, "status": status}


def advise(route: dict, value: int, items: list[dict], allotted_index: int, round_no: int) -> dict:
    """What MCC lets a student do after an allotment, and how their higher choices moved in past years."""
    if round_no not in MCC_ROUNDS:
        raise ValueError("round must be 1, 2, 3 or 4 (the stray vacancy round)")
    if not 0 <= allotted_index < len(items):
        raise ValueError("The allotted seat must be on the list")
    rules = MCC_ROUNDS[round_no]
    higher = []
    for index, item in enumerate(items[:allotted_index]):
        history = _history(route, item["key"], round_no, value) if item.get("key") else {"years": [], "status": "no_history"}
        higher.append({"position": index + 1, "institute": item.get("institute_short") or item["institute"], "programme": item["programme"], "quota": item["quota"], **history})
    hopeful = [h for h in higher if h["status"] in ("often", "sometimes")]
    allotted = items[allotted_index]
    if round_no >= 3:
        suggestion, why = "join", (
            "Round 3 was the last upgradation, so this seat is final." if round_no == 3 else "Stray round seats must be joined."
        )
    elif not higher:
        suggestion, why = "join", "This is your first choice, so no later round can move you higher. Freeze and join."
    elif hopeful:
        suggestion = "upgrade"
        why = (f"{len(hopeful)} higher choice{'s' if len(hopeful) != 1 else ''} on your list reached ranks like yours by Round 3 in past years. "
               "Choosing Float keeps this seat and lets MCC move you up if that happens again.")
    else:
        suggestion = "join"
        why = ("None of your higher choices reached ranks like yours by Round 3 in past years, so Freeze (joining now) is reasonable. "
               "Float still keeps this seat if you'd take a higher one.")
    return {
        "round": round_no, "round_label": rules["label"], "suggestion": suggestion, "why": why,
        "allotted": {"position": allotted_index + 1, "institute": allotted.get("institute_short") or allotted["institute"], "programme": allotted["programme"], "quota": allotted["quota"]},
        "options": rules["options"], "warning": rules.get("warning"), "higher_choices": higher,
        "source": BULLETIN,
        "cautions": [
            "This shows how the same seats moved in past years. This year's movement depends on other candidates' choices and can be different.",
            "Rules can change between years. Check MCC's bulletin and notices for this year before you act.",
            "Freeze or Float, upload your documents and act by MCC's deadline for the round, or you lose the seat.",
        ],
    }
