"""UPTAC (Uttar Pradesh) B.Tech: the reader, and the pointer from the JEE results."""
import json

import pytest

from app.schemas import StudentProfile
from app.services.recommend import state_routes
from ingest.exam_extract import UPTAC_HEADER, uptac_records, uptac_route


def row(n, round_label="R1: First Round", category="OPNO", gender="Co-Education", exam="JEE-MAIN", opening="1000", closing="5000"):
    return [str(n), round_label, "INSTITUTE OF ENGINEERING  AND TECHNOLOGY, LUCKNOW", "B.Tech (All Branches)/M.Tech (Integrated)",
            "Computer Science and Engineering", category, gender, exam, opening, closing, "-", "-", ""]


def save(tmp_path, rows, total=None):
    path = tmp_path / "uptac-2026-orcr-from-page.json"
    path.write_text(json.dumps({"header": UPTAC_HEADER, "total": total if total is not None else len(rows), "rows": rows}))
    return path


def test_reader_keeps_jee_main_rows_with_an_allotment(tmp_path):
    rows = [row(1), row(2, closing="-", opening="-"), row(3, round_label="R6: Special Round", exam="CUET-UG"), row(4, category="OPGL", gender="Female")]
    records, check = uptac_records(save(tmp_path, rows))
    assert [r["group"] for r in records] == ["Uttar Pradesh · Round 1", "Uttar Pradesh · Round 1"]
    assert records[0]["institute"] == "INSTITUTE OF ENGINEERING AND TECHNOLOGY, LUCKNOW"
    assert (records[0]["value"], records[0]["first_value"]) == (5000, 1000)
    assert records[1]["female_only"] and not records[0]["female_only"]
    assert check == {"rows": 4, "sequence_breaks": 0, "records": 2, "no_allotment": 1, "other_exam": 1}


def test_reader_refuses_a_short_save_or_unknown_round(tmp_path):
    with pytest.raises(SystemExit):
        uptac_records(save(tmp_path, [row(1)], total=2))
    with pytest.raises(SystemExit):
        uptac_records(save(tmp_path, [row(1, round_label="R9: Mystery")]))


def test_route_says_who_can_use_it(tmp_path):
    route = uptac_route(save(tmp_path, [row(1)]))
    assert route["code"] == "uptac" and route["metric"]["lower_is_better"]
    assert any("Class 12 in Uttar Pradesh" in limit for limit in route["limits"])


def test_jee_results_point_up_students_to_uptac():
    base = {"category": "GEN", "gender": "male", "class12_status": "meets", "main": {"crl": 300000}}
    assert state_routes(StudentProfile(**base, eligibility_state="Uttar Pradesh"))[0]["code"] == "uptac"
    assert state_routes(StudentProfile(**base, eligibility_state="Karnataka")) == []


def test_reader_takes_the_whole_rank(tmp_path):
    rows = [row(1, opening="41893.01", closing="65992"), row(2, round_label="R6: Special Round", exam="jee-main", opening="87671.0000000", closing="1476400.0000000")]
    records, _ = uptac_records(save(tmp_path, rows))
    assert [(r["first_value"], r["value"]) for r in records] == [(41893, 65992), (87671, 1476400)]
    assert records[1]["group"] == "Uttar Pradesh · Special round 1"
