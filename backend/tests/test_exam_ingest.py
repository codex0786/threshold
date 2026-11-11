import json

import pytest

from app.services.exam_routes import summary
from ingest.exam_extract import MH_SECTION, MH_STAGE, MH_TITLE, ccmt_records
from ingest.mcc_fees import fields, match

HEADER = ["SNo.", "Round", "Institute", "PG Program", "Group", "Category", "Max GATE Score", "Min GATE Score"]


def write_ccmt(tmp_path, rows, header=HEADER):
    path = tmp_path / "ccmt.json"
    path.write_text(json.dumps({"header": header, "rows": rows}))
    return path


def test_ccmt_rows_read_both_group_spellings_and_drop_exact_repeats(tmp_path):
    row = ["Round 2", "NIT X", "VLSI", "Group 1", "OPEN", "600", "550"]
    records, check = ccmt_records(write_ccmt(tmp_path, [
        row, row, ["Round 1", "NIT X", "VLSI", "G1", "OPEN", "640", "577"],
    ]))
    assert [r["group"] for r in records] == ["Group 1 · Round 1", "Group 1 · Round 2"]
    assert records[0]["value"] == 577 and records[0]["second_value"] == 640
    assert check == {"source_rows": 3, "repeated_rows": 1, "sequence_breaks": 0}


def test_ccmt_stops_on_an_unexpected_header_or_round(tmp_path):
    with pytest.raises(SystemExit):
        ccmt_records(write_ccmt(tmp_path, [], header=HEADER[:-1]))
    with pytest.raises(SystemExit):
        ccmt_records(write_ccmt(tmp_path, [["Round 9", "NIT X", "VLSI", "G1", "OPEN", "1", "1"]]))


def test_groups_follow_the_route_round_order_not_the_alphabet():
    route = {"rounds": ["CAP Round I, 2025-26", "CAP Round II, 2025-26", "CAP Round IV, 2025-26"], "metric": {}, "records": [
        {"institute": "A", "programme": "P", "category": "C", "value": 1, "group": g}
        for g in ["State Level, Stage I · CAP Round IV, 2025-26", "Home, Stage I · CAP Round II, 2025-26", "State Level, Stage I · CAP Round I, 2025-26"]
    ]}
    assert [g.rsplit(" · ", 1)[1] for g in summary(route)["groups"]] == route["rounds"]


def test_maharashtra_headings_stages_and_titles_as_published():
    assert MH_SECTION.match("Minority Seats Allotted to Maharashtra State Candidature Candidates")
    assert MH_SECTION.match("Maharashtra State Seats Allotted to All India Candidature Candidates")
    assert all(MH_STAGE.match(s) for s in ["I", "VII", "I-Non PWD", "I-Non Defence", "MH"])
    assert not MH_STAGE.match("Stage")
    assert MH_TITLE.search("CAP Round I for Admission ... for the Year 2025-26").groups() == ("I", "2025-26")
    assert MH_TITLE.search("CAP Round - IV for the Admission ... A.Y. 2025-26").groups() == ("IV", "2025-26")


def test_fee_form_fields_keep_multiline_labels_and_values_word_for_word():
    text = "\n".join([
        "Amount to be paid at the time of", "Admission(Including Hostel Fee 1st", "Year)in INR:",
        "Tuition fee: 29,00,000 and Hostel fee: 3,40,000 (Three seater non AC", "Room including mess facility)",
        "Annual Fees of Candidates(INR):", "0",
    ])
    assert fields(text) == {
        "Amount to be paid at the time of Admission(Including Hostel Fee 1st Year)in INR":
            "Tuition fee: 29,00,000 and Hostel fee: 3,40,000 (Three seater non AC Room including mess facility)",
        "Annual Fees of Candidates(INR)": "0",
    }


def test_fee_match_needs_exactly_one_institute():
    names = {"Kasturba Medical College, Mangalore,Light house Hill Road", "Kasturba Medical College, Manipal,Madhav Nagar"}
    assert match("Kasturba Medical College, Manipal", names) == "Kasturba Medical College, Manipal,Madhav Nagar"
    assert match("Kasturba Medical College", names) is None
