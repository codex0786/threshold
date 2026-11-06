"""Integration tests through the HTTP API against the test database and fixtures."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import pytest

from app.db import SessionLocal
from app.models import CutoffRecord, Institution, PlacementRecord, RecommendationRun


def profile(**kw):
    return {"category": "GEN", "gender": "male", "eligibility_state": "Karnataka", "class12_status": "meets", "main": {"crl": 12000}, **kw}


def generate(client, **kw):
    response = client.post("/api/v1/recommendations/generate", json={"profile": profile(**kw)})
    assert response.status_code == 200, response.text
    return response.json()


def by_name(result, inst, prog="Computer Science and Engineering"):
    return next((o for o in result["options"] if o["institution"]["short_name"] == inst and o["programme"] == prog), None)


def test_home_state_seat_is_used_for_home_candidate(client):
    option = by_name(generate(client), "Fixture NIT")
    assert option["best_route"]["quota"] == "HS" and option["band"] == "safer"


def test_same_rank_from_another_state_uses_other_state_seat(client):
    option = by_name(generate(client, eligibility_state="Punjab"), "Fixture NIT")
    # Other State closing rank is 5000 here, so a 12000 rank is well outside.
    assert option is None


def test_counselling_routes_are_not_mixed_between_exams(client):
    result = generate(client, main={"crl": 100})
    assert by_name(result, "Fixture IIT") is None
    with_adv = generate(client, main={"crl": 100}, advanced={"crl": 400}, advanced_qualified=True)
    assert by_name(with_adv, "Fixture IIT")["best_route"]["rank_list"] == "JEE_ADVANCED:CRL"


def test_category_rank_is_matched_only_to_category_seats(client):
    result = generate(client, category="OBC-NCL", eligibility_state="Karnataka", main={"crl": 90000, "category_rank": 1500})
    route = by_name(result, "Fixture NIT")["best_route"]
    assert route["seat_type"] == "OBC-NCL" and route["rank_used"] == 1500 and route["rank_list"] == "JEE_MAIN:OBC-NCL"


def test_crl_alone_never_unlocks_category_seat(client):
    result = generate(client, category="OBC-NCL", main={"crl": 1500})
    route = by_name(result, "Fixture NIT")["best_route"]
    assert route["seat_type"] == "OPEN" and route["rank_list"] == "JEE_MAIN:CRL"


def test_female_pool_only_for_female_candidates(client):
    punjab = {"eligibility_state": "Punjab", "main": {"crl": 8000}}
    assert by_name(generate(client, **punjab), "Fixture NIT") is None or by_name(generate(client, **punjab), "Fixture NIT")["best_route"]["gender_pool"] == "neutral"
    route = by_name(generate(client, gender="female", **punjab), "Fixture NIT")["best_route"]
    assert route["gender_pool"] == "female"


def test_architecture_needs_a_paper_two_rank(client):
    result = generate(client, main={"crl": 100})
    assert by_name(result, "Fixture NIT", "Architecture") is None


def test_preparatory_rank_is_never_a_cutoff(client):
    result = generate(client, category="SC", is_pwd=True, main={}, advanced={"crl": 400, "category_pwd_rank": 10}, advanced_qualified=True)
    route = by_name(result, "Fixture IIT")["best_route"]
    assert route["seat_type"] != "SC-PwD"


def test_goa_candidate_gets_goa_quota(client):
    route = by_name(generate(client, eligibility_state="Goa", main={"crl": 30000}), "Fixture NIT Goa")["best_route"]
    assert route["quota"] == "GO"


def test_missing_data_stays_missing(client):
    option = by_name(generate(client), "Fixture NIT")
    assert option["placements"] == [] and option["fee"] is None
    assert "No verified placement data" in option["data_gaps"] and "No verified fee data" in option["data_gaps"]
    assert option["quality"]["score"] is None and option["quality"]["status"] == "insufficient_evidence"


def test_institute_wide_placement_is_labelled_on_branch_view(client):
    option = by_name(generate(client, eligibility_state="Kerala", main={"crl": 20000}), "Fixture NIT Two")
    assert option["placements"][0]["scope"] == "institution"
    assert "not specific" in option["placements"][0]["scope_label"]
    assert any("institute-wide" in gap for gap in option["data_gaps"])


def test_schema_blocks_institute_data_stored_as_programme_data(seeded):
    with SessionLocal() as db:
        inst = db.scalar(select(Institution).where(Institution.slug == "fixture-nit"))
        doc_id = db.scalar(select(CutoffRecord.source_document_id).limit(1))
        db.add(PlacementRecord(institution_id=inst.id, programme_id=None, scope="programme", cohort_label="TEST cohort", reporting_definition="institute_placement_report", graduation_year=2020, verification_status="test_fixture", source_document_id=doc_id))
        with pytest.raises(IntegrityError):
            db.commit()


def test_historical_records_are_kept_per_year(client, seeded):
    response = client.get(f"/api/v1/programmes/{seeded['cse']}/cutoffs", params={"quota": "HS"}).json()
    assert [r["year"] for r in response["records"]] == [2024, 2025, 2026]
    assert "not admission probabilities" in response["note"]


def test_recommendations_are_reproducible_and_logged(client):
    first, second = generate(client), generate(client)
    assert first["result_hash"] == second["result_hash"] and first["options"] == second["options"]
    with SessionLocal() as db:
        row = db.scalars(select(RecommendationRun).order_by(RecommendationRun.id.desc())).first()
        assert row.result_hash == first["result_hash"]
        assert not any(k in row.input_snapshot for k in ("name", "email", "phone"))


def test_changing_priorities_reorders_results(client):
    rank_first = generate(client, eligibility_state="Punjab", main={"crl": 9000}, preferred_branches=["ECE"], priorities={"branch_fit": 5, "reputation": 95})
    branch_first = generate(client, eligibility_state="Punjab", main={"crl": 9000}, preferred_branches=["ECE"], priorities={"branch_fit": 95, "reputation": 5})
    order = lambda r: [(o["institution"]["short_name"], o["programme"]) for o in r["options"]]  # noqa: E731
    assert order(rank_first) != order(branch_first)
    assert branch_first["options"][0]["branch_family"] == "ECE"
    assert rank_first["options"][0]["institution"]["short_name"] == "Fixture NIT"


def test_seat_with_one_closing_rank_is_hidden_when_far_out_of_reach(client, seeded):
    ids = lambda r: {o["programme_id"] for o in r["options"]}  # noqa: E731
    near, far = generate(client, main={"crl": 21000}), generate(client, main={"crl": 500000})
    assert seeded["new_seat"] in ids(near) and seeded["new_seat"] not in ids(far)
    assert next(o for o in near["options"] if o["programme_id"] == seeded["new_seat"])["band"] is None
    assert far["excluded"]["beyond_range"] >= 1


def test_limited_history_seats_come_after_banded_seats(client):
    bands = [o["band"] for o in generate(client, main={"crl": 21000}, preferred_branches=["ROBOTICS"])["options"]]
    assert None in bands and None not in bands[:bands.index(None)] and set(bands[bands.index(None):]) == {None}


def test_programme_with_no_latest_cutoff_is_removed_and_counted(client, seeded):
    result = generate(client, main={"crl": 50000})
    assert seeded["old_seat"] not in {o["programme_id"] for o in result["options"]}
    assert result["excluded"]["no_latest_cutoff"] == 1


def test_how_contested_a_seat_is_orders_otherwise_equal_options(client, seeded):
    result = generate(client, main={"crl": 500}, eligibility_state="Goa", priorities={"demand": 100})
    programme_ids = [o["programme_id"] for o in result["options"]]
    assert programme_ids.index(seeded["cse"]) < programme_ids.index(seeded["civil"])
    component = next(c for c in by_name(result, "Fixture NIT")["suitability"]["components"] if c["key"] == "demand")
    assert "past candidates' choices, not quality" in component["note"]


def test_browser_profile_saved_before_the_contested_factor_gets_its_default(client):
    saved = {k: v for k, v in client.get("/api/v1/meta").json()["default_priorities"].items() if k != "demand"}
    components = generate(client, priorities=saved)["options"][0]["suitability"]["components"]
    assert next(c for c in components if c["key"] == "demand")["weight"] > 0


def test_avoided_branches_are_removed_and_counted(client):
    result = generate(client, main={"crl": 9000}, avoid_branches=["CIVIL"])
    assert all(o["branch_family"] != "CIVIL" for o in result["options"]) and result["excluded"]["avoided_branch"] >= 1


def test_class12_failure_returns_no_options_with_reason(client):
    result = generate(client, class12_status="does_not_meet")
    assert result["options"] == [] and any("75%" in w for w in result["warnings"])


def test_warnings_state_limits(client):
    warnings = " ".join(generate(client)["warnings"])
    assert "not guarantees or probabilities" in warnings and "CSAB" in warnings


def test_no_probability_in_any_response_field(client):
    def keys(value):
        if isinstance(value, dict):
            for k, v in value.items():
                yield k
                yield from keys(v)
        elif isinstance(value, list):
            for v in value:
                yield from keys(v)
    assert not any("prob" in k.lower() or "chance" in k.lower() for k in keys(generate(client)))


def test_validation_rejects_contradictions(client):
    post = lambda **kw: client.post("/api/v1/recommendations/generate", json={"profile": profile(**kw)}).status_code  # noqa: E731
    assert post(main={"crl": 10, "category_rank": 5}) == 422
    assert post(main={"crl": 10, "crl_pwd": 5}) == 422
    assert post(main={}) == 422
    assert post(main={"crl": -5}) == 422
    assert post(eligibility_state="Atlantis") == 422
    assert post(advanced_qualified=True) == 422
    assert post(preferred_branches=["CS"], avoid_branches=["CS"]) == 422


def test_comparison_limits_and_tradeoffs(client, seeded):
    ids = [seeded["cse"], seeded["cse_two"], seeded["ece_two"]]
    response = client.post("/api/v1/comparisons", json={"programme_ids": ids})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3 and body["trade_offs"]
    assert client.post("/api/v1/comparisons", json={"programme_ids": ids + [seeded["civil"], seeded["arch"]]}).status_code == 422
    assert client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse"]]}).status_code == 422
    assert client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse"], seeded["cse"]]}).status_code == 422
    assert client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse"], 999999]}).status_code == 404


def test_comparison_uses_student_route_when_profile_is_given(client, seeded):
    body = client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse"], seeded["cse_two"]], "profile": profile()}).json()
    assert body["items"][0]["student_route"]["quota"] == "HS" and body["items"][0]["suitability"]["score"] is not None


def test_discovery_filters(client):
    assert client.get("/api/v1/institutions", params={"type": "IIT"}).json()["total"] == 1
    assert client.get("/api/v1/institutions", params={"state": "Kerala"}).json()["items"][0]["slug"] == "fixture-nit-two"
    assert client.get("/api/v1/institutions", params={"q": "two"}).json()["total"] == 1
    assert client.get("/api/v1/institutions", params={"branch": "ECE"}).json()["total"] == 1
    assert client.get("/api/v1/institutions/does-not-exist").status_code == 404
    assert client.get("/api/v1/programmes/999999").status_code == 404


def test_tradeoffs_name_each_institute_once(client, seeded):
    body = client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse"], seeded["civil"], seeded["cse_two"]]}).json()
    assert body["items"][0]["ranking"] and all(note.count("Fixture NIT (10)") <= 1 for note in body["trade_offs"])


def test_read_only_mode_stores_no_student_input(client, monkeypatch):
    from sqlalchemy import func, select

    from app.config import settings
    from app.db import SessionLocal
    from app.models import RecommendationRun

    monkeypatch.setattr(settings, "read_only", True)
    profile = {"category": "GEN", "gender": "male", "is_pwd": False, "eligibility_state": "Karnataka", "class12_status": "meets", "main": {"crl": 15000}, "advanced": {}, "advanced_qualified": False}
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(RecommendationRun))
    assert client.post("/api/v1/recommendations/generate", json={"profile": profile}).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RecommendationRun)) == before


def test_rate_limit_returns_429_after_the_limit():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.rate_limit import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=2)
    app.get("/x")(lambda: {"ok": True})
    limited = TestClient(app)
    assert [limited.get("/x", headers={"x-forwarded-for": "1.1.1.1"}).status_code for _ in range(3)] == [200, 200, 429]
    assert limited.get("/x", headers={"x-forwarded-for": "2.2.2.2"}).status_code == 200


def ids_of(result):
    return {o["programme_id"] for o in result["options"]}


def goa_option(client, programme_id, **kw):
    result = generate(client, main={"crl": 70000}, **kw)
    return next((o for o in result["options"] if o["programme_id"] == programme_id), None), result


def test_renamed_programme_keeps_its_history_and_says_so(client, seeded):
    result = generate(client)
    option = next(o for o in result["options"] if o["programme_id"] == seeded["renamed_new"])
    assert set(option["best_route"]["years_used"]) == {2024, 2025, 2026} and option["band"] is not None
    assert option["earlier_names"] == [{"name": "Computer Engineering", "until": 2025}]
    assert seeded["renamed_old"] not in ids_of(result)


def test_renamed_programme_cutoffs_show_the_whole_history(client, seeded):
    records = client.get(f"/api/v1/programmes/{seeded['renamed_new']}/cutoffs?seat_type=OPEN").json()["records"]
    assert {r["year"] for r in records} == {2024, 2025, 2026}


def test_rename_does_not_mix_ranks_from_a_different_list(client, seeded):
    with SessionLocal() as db:
        lists = {r.rank_list for r in db.scalars(select(CutoffRecord).where(CutoffRecord.programme_id.in_([seeded["renamed_old"], seeded["renamed_new"]])))}
    assert len(lists) == 1


def test_campus_abroad_does_not_inherit_the_parent_institute(client, seeded):
    result = generate(client, advanced={"crl": 2000}, advanced_qualified=True)
    option = next(o for o in result["options"] if o["programme_id"] == seeded["abroad"])
    assert option["institution"]["city"] == "Abu Dhabi" and option["institution"]["state"] == "United Arab Emirates"
    assert "campus_note" in option["institution"]
    assert option["ranking"] is None and option["fee"] is None and all(p["scope"] == "programme" for p in option["placements"])


def test_thin_category_warns_and_shows_seats_without_changing_the_band(client, seeded):
    option, _ = goa_option(client, seeded["thin"])
    assert option["best_route"]["seats"] == 2 and any("Only 2 seats" in w for w in option["weaknesses"])
    assert option["band"] == "safer"


def test_past_cutoff_with_no_seat_this_year_is_removed(client, seeded):
    option, result = goa_option(client, seeded["gone"])
    assert option is None and result["excluded"]["no_seat_in_category"] >= 1


def test_seat_with_a_current_cutoff_stays(client, seeded):
    result = generate(client, category="SC", main={"crl": 70000, "category_rank": 70000})
    option = next(o for o in result["options"] if o["programme_id"] == seeded["gone"])
    assert option["best_route"]["seat_type"] == "SC" and option["best_route"]["seats"] == 3


def test_csab_is_listed_apart_and_never_changes_the_shortlist(client, seeded):
    result = generate(client, main={"crl": 350000}, eligibility_state="Tamil Nadu")
    assert result["options"] == [] and sum(result["counts"].values()) == 0
    assert result["csab"]["count"] >= 1 and "vacant" in result["csab"]["note"]
    assert all("band" not in o and o["closing_rank"] >= 350000 for o in result["csab"]["options"])


def test_csab_applies_quota_and_category_rules(client, seeded):
    other_state = generate(client, main={"crl": 350000}, eligibility_state="Tamil Nadu")["csab"]["options"]
    home = generate(client, main={"crl": 450000}, eligibility_state="Kerala")["csab"]["options"]
    assert {o["programme_id"] for o in other_state} == {seeded["civil"]}
    assert seeded["cse_two"] in {o["programme_id"] for o in home}
    assert all(o["seat_type"] == "OPEN" for o in other_state)
    sc = generate(client, category="SC", main={"crl": 550000, "category_rank": 9000}, eligibility_state="Tamil Nadu")["csab"]["options"]
    assert {(o["programme_id"], o["seat_type"]) for o in sc} == {(seeded["civil"], "SC")}


def test_completeness_reports_coverage_by_institute_type(client, seeded):
    body = client.get("/api/v1/data/completeness").json()
    assert body["by_type"]["NIT"]["institutions"] >= 3 and body["detail"]["renamed_programmes"] == 1
    assert "Seat matrix" not in body["not_yet_collected"]


def test_parent_report_and_comparison_give_the_campus_abroad_its_own_location(client, seeded):
    body = {"profile": profile(advanced={"crl": 2000}, advanced_qualified=True), "programme_ids": [seeded["abroad"], seeded["iit_cse"]]}
    report = client.post("/api/v1/reports/parent", json=body).json()
    place = {o["programme_id"]: o["institution"] for o in report["options"]}
    assert place[seeded["abroad"]]["city"] == "Abu Dhabi" and place[seeded["iit_cse"]]["city"] == "Z"
    compared = client.post("/api/v1/comparisons", json=body).json()["items"]
    assert compared[0]["institution"]["state"] == "United Arab Emirates" and compared[0]["ranking"] is None


def test_preference_list_points_an_old_name_to_the_new_one(client, seeded):
    items = client.post("/api/v1/preference-lists/analyse", json={"profile": profile(), "programme_ids": [seeded["renamed_old"], seeded["renamed_new"]]}).json()["items"]
    assert "Computer Engineering and Systems" in items[0]["issues"][0]
    assert not any("cutoff" in issue for issue in items[1]["issues"])
    assert items[1]["band"] is not None


def test_institute_shows_faculty_indicators_separately_with_a_source(client):
    body = client.get("/api/v1/institutions/fixture-nit").json()["academics"]
    assert body["teaching"]["students_per_regular_faculty"] == 15.0 and body["experience"]["phd_share"] == 0.9
    assert body["availability"]["faculty_other_current"] == 10 and body["research"]["years"][0]["sponsored_amount_inr"] == 50_000_000
    assert body["source"]["title"] and "teach" in body["teaching"]["note"] and "not this department" in body["scope_note"]


def test_missing_faculty_data_stays_missing(client, seeded):
    assert client.get("/api/v1/institutions/fixture-goa").json()["academics"] is None
    body = client.get(f"/api/v1/programmes/{seeded['goa_cse']}/faculty").json()
    assert body["status"] == "Data not available" and body["institute_wide"] is None


def test_programme_faculty_is_never_presented_as_department_data(client, seeded):
    body = client.get(f"/api/v1/programmes/{seeded['cse']}/faculty").json()
    assert body["department_level"] is None and body["status"] == "institute_wide" and body["institute_wide"]["teaching"]


def test_faculty_sliders_change_order_not_bands(client):
    before = {o["programme_id"]: o["band"] for o in generate(client)["options"]}
    after = {o["programme_id"]: o["band"] for o in generate(client, priorities={"branch_fit": 10, "faculty": 90, "research": 90})["options"]}
    assert before == after


def ask(client, question, **kw):
    response = client.post("/api/v1/ai/counselling", json={"question": question, **kw})
    assert response.status_code == 200, response.text
    return response.json()


def test_assistant_states_it_uses_no_model_and_never_stores_the_question(client):
    with SessionLocal() as db:
        runs = db.scalar(select(func.count()).select_from(RecommendationRun))
    assert ask(client, "What is the difference between float and slide?")["uses_ai_model"] is False
    ask(client, "Fees at Fixture NIT", profile=profile())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RecommendationRun)) == runs


def test_assistant_rules_answers_cite_the_official_rules(client):
    answer = ask(client, "What is the difference between float and slide?")
    assert answer["tool"] == "joint_seat_rules" and len(answer["facts"]) >= 3
    assert all("Business Rules" in f["source_title"] and f["source_url"] for f in answer["facts"])


def test_assistant_compares_without_picking_and_labels_reasoning(client):
    answer = ask(client, "Should I choose Fixture NIT CSE or Fixture NIT Two ECE?")
    assert answer["tool"] == "compare_programmes" and "won't pick" in answer["summary"]
    assert any("Fixture NIT Two" in f["text"] for f in answer["facts"])
    assert all(f["source_url"] for f in answer["facts"])


def test_assistant_uses_a_rank_only_as_a_band_never_a_percentage(client):
    text = str(ask(client, "What is my chance at Fixture NIT CSE?", profile=profile()))
    assert "band" in text and "%" not in text.replace("20%", "").replace("10%", "")
    assert "chance of admission" in text


def test_assistant_says_when_it_recognised_only_one_option(client):
    answer = ask(client, "Fixture NIT CSE or Some Unknown College CSE")
    assert "only recognised Fixture NIT" in answer["summary"] and answer["tool"] == "institute_records"


def test_assistant_gives_no_verdicts_or_teacher_ratings(client):
    assert "can't tell you" in ask(client, "Is Fixture NIT good?")["summary"]
    assert "don't rate" in ask(client, "Who is the best professor at Fixture NIT?")["summary"]


def test_assistant_reports_missing_data_instead_of_inventing_it(client):
    answer = ask(client, "Faculty at Fixture NIT Goa")
    assert answer["facts"] == [] and any("No NIRF faculty" in g for g in answer["gaps"])
    assert ask(client, "What's the weather?")["tool"] == "not_understood"


def test_assistant_asks_for_a_rank_it_doesnt_have(client):
    answer = ask(client, "Which college can I get?")
    assert answer["needs_profile"] is True and answer["facts"] == []
    assert ask(client, "Which college can I get?", profile=profile())["facts"]


def test_assistant_value_answer_never_uses_a_branch_median_for_an_institute(client):
    text = str(ask(client, "Best value under 100 lakh")["facts"])
    assert "Fixture NIT Goa" in text and "No institute-wide median" in text and "12.34 lakh" not in text


def test_assistant_rejects_an_oversized_question(client):
    assert client.post("/api/v1/ai/counselling", json={"question": "x" * 501}).status_code == 422

