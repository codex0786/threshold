"""Shortlist positions for exam routes: one year, placed by the round that first reached the student."""
from app.services import exam_routes

ROUNDS = ["Round 1", "Round 2", "Round 3", "Stray round"]


def route(records, lower=True, rounds=ROUNDS):
    r = {
        "code": "t", "stream": "Medical", "rounds": rounds, "compare_requires_group": True,
        "metric": {"label": "Rank", "unit": "rank", "lower_is_better": lower, "whole_number": lower, "value_label": "Last rank allotted", "second_label": None},
        "records": records,
    }
    exam_routes.add_standing(r)
    return r


def seat(institute, figures, quota="All India", category="Open"):
    return [
        {"institute": institute, "programme": "MBBS", "group": f"{quota} · {rnd}", "category": category, "value": v}
        for rnd, v in zip(ROUNDS, figures) if v is not None
    ]


def positions(r, value, **kw):
    out = exam_routes.shortlist(r, value, "Open", "All India", **kw)
    return {o["institute"]: o["position"] for o in out["options"]}, out


def test_positions_by_first_round_reached():
    r = route(seat("A", [1200, 1500, 1600, 9000]) + seat("B", [800, 1100, 1300, 9000]) + seat("C", [500, 600, 700, 1150])
              + seat("D", [500, 600, 700, 950]) + seat("E", [100, 200, 300, 400]))
    got, out = positions(r, 1000)
    assert got == {"A": "first_round", "B": "later_round", "C": "leftover_round", "D": "near"}
    assert out["beyond"] == 1 and out["counts"]["first_round"] == 1


def test_round_ladder_keeps_round_order_and_flags():
    r = route(seat("A", [1200, 900, 1500, None]))
    _, out = positions(r, 1000)
    ladder = out["options"][0]["rounds"]
    assert [s["round"] for s in ladder] == ROUNDS[:3]
    assert [s["reached"] for s in ladder] == [True, False, True]
    assert any("didn't reach your rank in Round 2" in w for w in out["options"][0]["why"])


def test_higher_is_better_has_no_near_position():
    records = [{"institute": "A", "programme": "P", "group": "G · Round 1", "category": "Open", "value": 95.5}]
    r = route(records, lower=False, rounds=["Round 1"])
    out = exam_routes.shortlist(r, 90.0, "Open", "G")
    assert out["options"] == [] and out["beyond"] == 1
    assert exam_routes.shortlist(r, 99.0, "Open", "G")["options"][0]["position"] == "first_round"


def test_needs_figure_category_and_quota():
    r = route(seat("A", [1200, None, None, None]))
    assert exam_routes.shortlist(r, None, None, None)["missing"] == ["figure", "category", "quota"]
    assert exam_routes.shortlist(r, 1000, "Open", "Other quota")["options"] == []


def test_female_only_seats_hidden_for_male_candidates():
    rows = seat("A", [1200, None, None, None])
    rows[0]["female_only"] = True
    r = route(rows)
    assert exam_routes.shortlist(r, 1000, "Open", "All India", gender="male")["hidden_female_only"] == 1
    assert exam_routes.shortlist(r, 1000, "Open", "All India", gender="female")["options"][0]["female_only"]


def test_no_probability_fields():
    r = route(seat("A", [1200, 1500, 1600, 9000]))
    out = exam_routes.shortlist(r, 1000, "Open", "All India")
    keys = set(out) | {k for o in out["options"] for k in o}
    assert not any("prob" in k or "chance" in k or "likel" in k for k in keys)
