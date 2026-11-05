"""Financial, preference-list and parent-report rules. Figures are constructed test inputs."""
import pytest

from app.services import finance


def profile(**kw):
    return {"category": "GEN", "gender": "male", "eligibility_state": "Karnataka", "class12_status": "meets", "main": {"crl": 12000}, **kw}


def test_total_cost_adds_annual_one_time_and_deposit():
    c = finance.total_cost(finance.CostInputs(100, 20, 30, 10, 500, 200, 40, 50, 4))
    assert c["annual_cost"] == 200 and c["annual_after_scholarship"] == 150
    assert c["total_cost"] == 150 * 4 + 700 and c["total_excluding_refundable"] == c["total_cost"] - 200


def test_scholarship_cannot_make_cost_negative():
    assert finance.total_cost(finance.CostInputs(100, 0, 0, 0, 0, 0, 0, 500, 4))["total_cost"] == 0


def test_emi_matches_the_standard_formula():
    assert round(finance.emi(1000000, 12, 10)) == 14347
    assert finance.emi(120000, 0, 1) == 10000
    assert finance.emi(0, 9, 10) == 0


def test_loan_adds_moratorium_interest():
    terms = finance.loan(1000000, 10, 10, 60)
    assert terms["interest_during_moratorium"] == 500000 and terms["balance_at_repayment"] == 1500000
    assert terms["total_interest"] == terms["total_repaid"] - 1000000


def test_salary_scenarios_are_built_from_the_median_and_need_one():
    assert finance.salary_scenarios(None, None, None) is None
    assert finance.salary_scenarios(1000000, None, None) == {"Low": 700000, "Base": 1000000, "High": 1300000}
    assert finance.salary_scenarios(1000000, 500000, 2000000)["Low"] == 500000


def test_scenario_flags_an_unaffordable_emi():
    assert finance.scenario("Low", 600000, 0.7, 0.4, 20000, 1000000)["emi_warning"] is True
    assert finance.scenario("High", 2400000, 0.7, 0.4, 20000, 1000000)["emi_warning"] is False


def test_roi_api_has_no_scenarios_without_a_median_and_always_warns(client):
    body = client.post("/api/v1/financial/roi", json={"annual_tuition_inr": 100000}).json()
    assert body["scenarios"] == [] and "not a guaranteed return" in body["warning"]
    assert body["costs"]["total_cost"] == 400000 and body["loan"]["loan_amount"] == 400000


def test_roi_api_labels_assumed_salaries_and_rejects_bad_input(client):
    body = client.post("/api/v1/financial/roi", json={"annual_tuition_inr": 100000, "median_ctc_inr": 1000000, "family_contribution_inr": 100000}).json()
    assert [s["name"] for s in body["scenarios"]] == ["Low", "Base", "High"] and body["assumptions"]["low_is_assumed"] is True
    assert body["loan"]["loan_amount"] == 300000
    assert client.post("/api/v1/financial/roi", json={"interest_rate_percent": 99}).status_code == 422
    assert client.post("/api/v1/financial/roi", json={"annual_tuition_inr": -1}).status_code == 422


def analyse(client, ids, **kw):
    response = client.post("/api/v1/preference-lists/analyse", json={"profile": profile(**kw), "programme_ids": ids})
    assert response.status_code == 200, response.text
    return response.json()


def test_preference_order_is_never_changed(client, seeded):
    ids = [seeded["civil"], seeded["cse"], seeded["cse_two"]]
    body = analyse(client, ids)
    assert [i["programme_id"] for i in body["items"]] == ids and body["order_preserved"] is True
    reverse = analyse(client, ids[::-1])
    assert [i["programme_id"] for i in reverse["items"]] == ids[::-1]


def test_ambitious_choice_below_a_safer_one_is_flagged_but_left_in_place(client, seeded):
    # Karnataka candidate at 12000: home-state CSE (20000) is safer, Kerala CSE as Other State (11000) is ambitious.
    ids = [seeded["cse"], seeded["cse_two"]]
    body = analyse(client, ids)
    assert body["items"][0]["band"] == "safer" and body["items"][1]["band"] == "ambitious"
    assert any("may never be reached" in a for a in body["advice"]) and [i["programme_id"] for i in body["items"]] == ids
    assert not any("may never be reached" in a for a in analyse(client, ids[::-1])["advice"])


def test_a_list_with_no_safer_choice_is_flagged(client, seeded):
    body = analyse(client, [seeded["cse_two"]])
    assert any("None of these choices" in a for a in body["advice"])


def test_iit_without_advanced_and_architecture_are_explained(client, seeded):
    items = analyse(client, [seeded["iit_cse"], seeded["arch"]])["items"]
    assert items[0]["status"] == "no_route" and any("JEE Advanced" in i for i in items[0]["issues"])
    assert items[1]["status"] == "no_route" and any("different exam paper" in i for i in items[1]["issues"])


def test_preference_analysis_uses_the_right_rank_list(client, seeded):
    item = analyse(client, [seeded["cse"]], category="OBC-NCL", main={"crl": 90000, "category_rank": 1500})["items"][0]
    assert item["routes"][0]["seat_type"] == "OBC-NCL" and item["routes"][0]["rank_list"] == "JEE_MAIN:OBC-NCL"


def test_duplicates_are_flagged_and_limits_enforced(client, seeded):
    assert any("more than once" in a for a in analyse(client, [seeded["cse"], seeded["cse"]])["advice"])
    assert client.post("/api/v1/preference-lists/analyse", json={"profile": profile(), "programme_ids": []}).status_code == 422


def test_parent_report_states_limits_and_stays_honest_about_gaps(client, seeded):
    response = client.post("/api/v1/reports/parent", json={"profile": profile(), "programme_ids": [seeded["cse"], seeded["cse_two"]]})
    assert response.status_code == 200
    body = response.json()
    assert [o["programme_id"] for o in body["options"]] == [seeded["cse"], seeded["cse_two"]]
    assert any("doesn't guarantee" in limit for limit in body["limits"])
    first = body["options"][0]
    assert first["placement_highlight"] is None or first["placement_highlight"]["median_salary_inr"]
    assert any("fee" in r.lower() for r in first["risks"])
    assert "name" not in body["student"] and "email" not in body["student"]


def test_parent_report_rejects_unknown_programmes(client, seeded):
    assert client.post("/api/v1/reports/parent", json={"profile": profile(), "programme_ids": [999999]}).status_code == 404


def test_salary_defaults_use_the_newest_year_and_prefer_the_branch():
    from types import SimpleNamespace as N
    from app.services.recommend import best_salary_record
    old = N(scope="institution", median_salary_inr=1800000, graduation_year=2022)
    new = N(scope="institution", median_salary_inr=1700000, graduation_year=2024)
    branch = N(scope="programme", median_salary_inr=1000000, graduation_year=2023)
    assert best_salary_record([old, new]) is new
    assert best_salary_record([old, new, branch]) is branch
    assert best_salary_record([N(scope="programme", median_salary_inr=None, graduation_year=2025), new]) is new
    assert best_salary_record([]) is None


def test_parent_report_refers_to_the_student(client, seeded):
    body = client.post("/api/v1/reports/parent", json={"profile": profile(), "programme_ids": [seeded["cse"]]}).json()
    assert "The student's rank" in body["options"][0]["admission"]["routes"][0]["explanation"]
