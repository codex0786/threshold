"""NEET choice lists and MCC round advice."""
import pytest

from app.services import exam_lists, exam_routes
from tests.test_exam_shortlist import route, seat


def neet(records, closing, by_round):
    r = route(records)
    r["code"] = "neet-ug"
    r["history"] = {"years": [2024, 2025, 2026], "institutes": {exam_routes._squash(x["institute"]): x["institute"].lower() for x in records},
                    "closing": closing, "by_round": by_round}
    return r


def key(name):
    return f"{name.lower()}|MBBS|allindia|Open"


@pytest.fixture
def r():
    records = seat("Top", [800, 900, 1000, None]) + seat("Mid", [2500, 2700, 2900, None]) + seat("Safe", [6000, 6500, 7000, None])
    closing = {key("Top"): {"2024": 1100, "2025": 1000, "2026": 1000}, key("Mid"): {"2024": 3000, "2025": 2950, "2026": 2900},
               key("Safe"): {"2024": 7000, "2025": 7200, "2026": 7000}}
    by_round = {key("Top"): {"2024": [900, 1000, 1100], "2025": [800, 950, 1000]},
                key("Mid"): {"2024": [2400, 2800, 3100], "2025": [2500, 2900, 3000], "2026": [2500, 2700, 2960]},
                key("Safe"): {"2024": [6000, 6500, 7000]}}
    for x in records:
        x["standing"] = {"Top": 90, "Mid": 60, "Safe": 30}[x["institute"]]
    return neet(records, closing, by_round)


def test_the_list_runs_top_first_and_ends_at_the_safety_net(r):
    built = exam_lists.build(r, 2950, "Open", ["All India"], safety_net=1)
    assert [i["institute"] for i in built["items"]] == ["Mid", "Safe"]
    assert built["stop_reason"] == "safety_net_complete" and built["counts"]["safer"] == 1


def test_round_advice_suggests_upgradation_when_a_higher_choice_opened_up_by_round_3(r):
    items = exam_lists.build(r, 2950, "Open", ["All India"], safety_net=1)["items"]
    advice = exam_lists.advise(r, 2950, items, allotted_index=1, round_no=1)
    assert advice["suggestion"] == "upgrade" and advice["higher_choices"][0]["status"] == "often"
    assert [o["key"] for o in advice["options"]] == ["upgrade", "join", "free_exit"]
    assert exam_lists.advise(r, 2950, items, allotted_index=1, round_no=3)["suggestion"] == "join"
    assert "forfeits" in exam_lists.advise(r, 2950, items, allotted_index=1, round_no=2)["warning"]


def test_first_choice_and_unknown_rounds(r):
    items = exam_lists.build(r, 2950, "Open", ["All India"], safety_net=1)["items"]
    assert exam_lists.advise(r, 2950, items, allotted_index=0, round_no=1)["suggestion"] == "join"
    with pytest.raises(ValueError):
        exam_lists.advise(r, 2950, items, allotted_index=0, round_no=5)


def test_only_neet_with_round_history_has_list_tools(client):
    routes = {x["code"]: x["list_tools"] for x in client.get("/api/v1/exams").json()["routes"]}
    assert all(not v for c, v in routes.items() if c != "neet-ug")
    assert client.post("/api/v1/exams/clat/list/build", json={"value": 5, "category": "x", "quotas": ["y"]}).status_code in (404, 422)
