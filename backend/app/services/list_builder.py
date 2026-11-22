"""Suggest a JoSAA choice list from the shortlist. A starting point the student edits, never a submission.

The order follows the shortlist's own order (top institutes first, or the student's fit), because JoSAA
gives you the highest choice you qualify for: a list should be ordered by what you want, not by likelihood.
What the builder adds is the safety net. It keeps a number of Safer options in the list, and it stops
once that many are in, because choices placed below several Safer ones are rarely reached.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas import StudentProfile
from app.services import recommend as rec

BANDED = ("safer", "competitive", "ambitious")


def build(db: Session, profile: StudentProfile, order: str = "top", size: int = 60, safety_net: int = 5, include_ambitious: bool = True, past_safety_net: bool = False) -> dict:
    result = rec.generate(db, profile, per_band_limit=10_000, record_run=False, order=order)
    candidates = [o for o in result["options"] if o["band"] in BANDED and (include_ambitious or o["band"] != "ambitious")]
    safer_available = sum(1 for o in candidates if o["band"] == "safer")
    net = min(safety_net, safer_available)

    chosen: list[dict] = []
    safer_in = 0
    stop_reason = "ran_out"
    for option in candidates:
        if safer_in >= net and net > 0 and not past_safety_net:
            stop_reason = "safety_net_complete"
            break
        if len(chosen) >= size:
            stop_reason = "size_reached"
            break
        slots_left = size - len(chosen)
        # Keep the last slots for the safety net, so a long run of ambitious options can't crowd it out.
        if option["band"] != "safer" and slots_left <= net - safer_in:
            continue
        if option["band"] == "safer":
            safer_in += 1
        chosen.append(option)
    else:
        stop_reason = "safety_net_complete" if net and safer_in >= net and not past_safety_net else "ran_out"

    position_label = "top institutes first" if order == "top" else "your fit"
    items = []
    for i, o in enumerate(chosen, start=1):
        reason = f"In shortlist order ({position_label})."
        if past_safety_net and o["band"] == "safer" and sum(1 for c in chosen[:i] if c["band"] == "safer") > net:
            reason = "Past your safety net: kept because you asked for a longer list. Past rounds rarely reached this far down."
        elif o["band"] == "safer" and (past_safety_net or i > len(chosen) - net):
            reason = "Part of your safety net: past closing ranks were comfortably beyond your rank."
        items.append({
            "position": i, "programme_id": o["programme_id"], "programme": o["programme"],
            "degree": o.get("degree"), "duration_years": o.get("duration_years"),
            "institution": o["institution"]["short_name"], "institution_slug": o["institution"]["slug"],
            "band": o["band"], "reason": reason, "explanation": o["best_route"]["explanation"],
        })

    counts = {b: sum(1 for i in items if i["band"] == b) for b in BANDED}
    notes = []
    if stop_reason == "safety_net_complete":
        notes.append(f"The list stops after {net} Safer options. Past cutoffs suggest choices below them would rarely be reached, so adding more mostly lengthens the list.")
        if len(chosen) < size and all(i["band"] == "safer" for i in chosen):
            notes.append(f"It's short because every option here was Safer for your rank: JoSAA would very likely give you one of the first choices, so put the ones you want most at the top.")
    if past_safety_net and safer_in > net:
        notes.append(f"You asked to keep going past the safety net, so the list has {safer_in} Safer options instead of stopping at {net}. Choices well below your safety net are rarely reached, but listing them costs nothing in JoSAA.")
    if stop_reason == "size_reached":
        notes.append(f"The list reached the {size} choices you asked for before the safety net filled. Consider a longer list or fewer ambitious options.")
    if chosen and safer_available < safety_net:
        notes.append(f"Only {safer_available} Safer option{'s' if safer_available != 1 else ''} matched your profile, so the safety net is thinner than the {safety_net} you asked for. Add acceptable branches, institute types or states to widen it.")
    if not chosen:
        # An empty list shows its first note as the error, so the plainest explanation goes first.
        notes.insert(0, "No JoSAA option has reached a rank like yours in recent years, so there's no list to build. Check your ranks and Class XII state. State counselling may still have seats.")
    skipped_limited = result["counts"].get("limited_history", 0)
    if skipped_limited:
        notes.append(f"{skipped_limited} option{'s' if skipped_limited != 1 else ''} with limited history {'were' if skipped_limited != 1 else 'was'} left out, because one year of cutoffs can't place them. Add them by hand if you want them.")
    # An empty list shows its first note as the error, so the IIT notice goes first only when there is a list.
    if chosen and (notice := rec.advanced_notice(profile)):
        notes.insert(0, notice)
    notes.append("Move anything you'd prefer higher. Order by what you want most: JoSAA will give you the highest choice your rank reaches.")
    return {
        "items": items, "counts": counts, "order": order, "size": size, "safety_net": safety_net, "stop_reason": stop_reason,
        "notes": notes, "data_year": result.get("data_year"), "engine_version": result.get("engine_version"),
    }
