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


def test_main_round_seats_come_before_stray_only_and_near_seats():
    # C is reached only in the stray round, D never reaches 1000, A in round 1. C and D would lead on standing alone.
    r = route(seat("A", [1200, 1500, 1600, 9000]) + seat("C", [500, 600, 700, 1150]) + seat("D", [500, 600, 700, 950]))
    for record in r["records"]:
        record["standing"] = {"A": 10, "C": 90, "D": 99}[record["institute"]]
    got, _ = positions(r, 1000)
    out = exam_routes.shortlist(r, 1000, "Open", "All India")
    assert [o["institute"] for o in out["options"]] == ["A", "C", "D"]


def test_an_empty_list_points_to_quotas_and_courses_that_reached_the_figure():
    r = route(seat("A", [500, 600, 700, 800]) + seat("B", [5000, 5200, 5300, None], quota="Self-Financed Merit Seat")
              + seat("C", [4000, 4100, None, None], quota="Non-Resident Indian") + seat("D", [9000, None, None, None], quota="Non-Resident Indian", category="OBC"))
    out = exam_routes.shortlist(r, 3000, "Open", "All India")
    assert out["options"] == [] or all(o["position"] == "near" for o in out["options"])
    assert out["elsewhere"] == [{"quota": "Non-Resident Indian", "programme": "MBBS", "seats": 1}, {"quota": "Self-Financed Merit Seat", "programme": "MBBS", "seats": 1}]
    # A full list doesn't need it.
    many = route(sum((seat(f"X{i}", [5000, None, None, None]) for i in range(12)), []) + seat("B", [5000, None, None, None], quota="Non-Resident Indian"))
    assert exam_routes.shortlist(many, 3000, "Open", "All India")["elsewhere"] == []


def test_categories_are_offered_per_quota():
    r = route([
        {"institute": "A", "programme": "Civil", "group": "Home University, Stage I · Round 1", "category": "GOPENH", "value": 90.0},
        {"institute": "A", "programme": "Civil", "group": "State Level, Stage I · Round 1", "category": "GOPENS", "value": 95.0},
    ], lower=False, rounds=["Round 1"])
    assert exam_routes.quota_categories(r) == {"Home University, Stage I": ["GOPENH"], "State Level, Stage I": ["GOPENS"]}


def test_routes_with_few_nirf_ranks_order_by_contest_across_courses():
    rows = [{"institute": name, "programme": course, "group": "Q · Round 1", "category": "Open", "value": v, **({"ranking": {"rank": 1}} if ranked else {})}
            for name, course, v, ranked in (("Ranked", "Civil", 5000, True), ("Sought", "Computer", 100, False), ("Other", "Civil", 4000, False))]
    r = route(rows, rounds=["Round 1"])
    assert r["standing_basis"] == "contest"
    by = {x["institute"]: x["standing"] for x in r["records"]}
    # One NIRF rank no longer lifts a barely contested seat above the most sought-after one.
    assert by["Sought"] > by["Other"] > by["Ranked"]


def test_state_categories_point_past_the_national_cut_offs():
    from app.services.exam_routes import state_categories
    route = {
        "metric": {"lower_is_better": True},
        "category_states": {"General Category of Goa (GC-GA)": "Goa", "Scheduled Caste of Goa (SC-GA)": "Goa"},
        "records": [
            {"institute": "U1", "programme": "BA LLB", "category": "General (General)", "value": 3000},
            {"institute": "U2", "programme": "BA LLB", "category": "General Category of Goa (GC-GA)", "value": 12000},
            {"institute": "U2", "programme": "BBA LLB", "category": "General Category of Goa (GC-GA)", "value": 9000},
            {"institute": "U2", "programme": "BA LLB", "category": "Scheduled Caste of Goa (SC-GA)", "value": 40000},
        ],
    }
    assert state_categories(route, 10000, "General (General)") == [{"state": "Goa", "category": "General Category of Goa (GC-GA)", "seats": 1}]
    assert state_categories(route, 10000, "Women (W)") == []
