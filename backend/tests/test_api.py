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
