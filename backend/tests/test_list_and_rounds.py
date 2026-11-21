"""The list builder and the round companion, through the HTTP API on the test fixtures."""
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import CutoffRecord


def profile(**kw):
    return {"category": "GEN", "gender": "male", "eligibility_state": "Karnataka", "class12_status": "meets", "main": {"crl": 12000}, **kw}


def build(client, **body):
    response = client.post("/api/v1/preference-lists/build", json={"profile": profile(**body.pop("p", {})), **body})
    assert response.status_code == 200, response.text
    return response.json()


def test_builder_keeps_shortlist_order_and_only_banded_options(client):
    built = build(client, order="top", size=60, safety_net=20)
    shortlist = client.post("/api/v1/recommendations/generate", json={"profile": profile(), "order": "top"}).json()
    banded = [o["programme_id"] for o in shortlist["options"] if o["band"]]
    ids = [i["programme_id"] for i in built["items"]]
    assert ids == [pid for pid in banded if pid in ids]
    assert all(i["band"] in ("safer", "competitive", "ambitious") for i in built["items"])


def test_builder_stops_once_the_safety_net_is_full(client):
    built = build(client, safety_net=1)
    safer_positions = [i["position"] for i in built["items"] if i["band"] == "safer"]
    assert len(safer_positions) == 1 and safer_positions[0] == len(built["items"])
    assert built["stop_reason"] == "safety_net_complete"


def test_builder_reserves_slots_for_the_safety_net(client):
    built = build(client, size=5, safety_net=2)
    assert len(built["items"]) <= 5
    shortlist = client.post("/api/v1/recommendations/generate", json={"profile": profile(), "per_band_limit": 100}).json()
    assert built["counts"]["safer"] == min(2, shortlist["counts"].get("safer", 0))


def test_builder_can_leave_out_ambitious_options(client):
    built = build(client, include_ambitious=False, safety_net=20)
    assert all(i["band"] != "ambitious" for i in built["items"])


def test_builder_validates_size(client):
    assert client.post("/api/v1/preference-lists/build", json={"profile": profile(), "size": 500}).status_code == 422


@pytest.fixture()
def round_one(seeded):
    # Round 1 closed tighter than the final round for Fixture NIT Two's CSE (Other State, OPEN), as seats often do.
    with SessionLocal() as db:
        doc_id = db.query(CutoffRecord.source_document_id).first()[0]
        for year in (2024, 2025, 2026):
            db.add(CutoffRecord(
                programme_id=seeded["cse_two"], authority="JOSAA", year=year, round=1, is_final_round=False, quota="OS", seat_type="OPEN",
                gender_pool="neutral", rank_list="JEE_MAIN:CRL", opening_rank=1000, closing_rank=9000, is_preparatory=False,
                raw_opening="1000", raw_closing="9000", source_document_id=doc_id,
            ))
        db.commit()
    yield seeded
    with SessionLocal() as db:
        db.execute(delete(CutoffRecord).where(CutoffRecord.round == 1, CutoffRecord.programme_id == seeded["cse_two"]))
        db.commit()


def advice(client, ids, allotted, rank, round_no=1):
    response = client.post("/api/v1/rounds/advice", json={"profile": profile(main={"crl": rank}), "programme_ids": ids, "allotted_programme_id": allotted, "round": round_no})
    assert response.status_code == 200, response.text
    return response.json()


def test_float_when_a_higher_choice_elsewhere_opened_up_in_later_rounds(client, round_one):
    ids = [round_one["cse_two"], round_one["civil"]]
    result = advice(client, ids, round_one["civil"], 10000)
    assert result["suggestion"] == "float"
    top = result["higher_choices"][0]
    assert top["status"] == "often" and top["opened_later_years"] == 3
    assert top["years"][0]["closing_at_round"] == 9000 and top["years"][0]["final_closing"] == 11000


def test_slide_when_only_the_same_institute_is_within_reach(client, seeded):
    ids = [seeded["cse_two"], seeded["cse"], seeded["civil"]]
    result = advice(client, ids, seeded["civil"], 18000, round_no=2)
    assert result["suggestion"] == "slide"


def test_freeze_when_nothing_higher_was_reached(client, seeded):
    result = advice(client, [seeded["cse"], seeded["civil"]], seeded["civil"], 25000, round_no=2)
    assert result["suggestion"] == "freeze"


def test_freeze_on_the_first_choice_and_in_the_last_round(client, seeded):
    assert advice(client, [seeded["civil"], seeded["cse"]], seeded["civil"], 12000)["suggestion"] == "freeze"
    assert advice(client, [seeded["cse_two"], seeded["civil"]], seeded["civil"], 10000, round_no=5)["suggestion"] == "freeze"


def test_round_advice_rejects_a_seat_not_on_the_list(client, seeded):
    response = client.post("/api/v1/rounds/advice", json={"profile": profile(), "programme_ids": [seeded["cse"]], "allotted_programme_id": seeded["civil"], "round": 1})
    assert response.status_code == 422


def test_course_cost_is_a_minimum_when_the_fee_record_is_partial(client, seeded):
    response = client.post("/api/v1/comparisons", json={"programme_ids": [seeded["goa_cse"], seeded["cse"]]})
    assert response.status_code == 200
    by_id = {i["programme_id"]: i for i in response.json()["items"]}
    partial = by_id[seeded["goa_cse"]]["course_cost"]
    assert partial["status"] == "at_least" and "hostel" in partial["missing"]
    assert partial["total_inr"] == partial["annual_inr"] * partial["years"] + partial["one_time_inr"]
