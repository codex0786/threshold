"""NEET UG history: reading MCC's round tables, linking institute spellings across years, and bands on the shortlist."""
from ingest import neet_history as nh

from tests.test_exam_shortlist import route, seat
from app.services import exam_routes


def test_round_one_and_stray_rows_read_rank_and_seat():
    rows = [["SNo", "Rank", "Allotted Quota", "Allotted Institute", "Course", "Alloted Category", "Candidate Category", "Remarks"],
            ["1", "1(A)", "Open Seat Quota", "JIPMER PUDUCHERRY,Dhanvantari Nagar", "MBBS", "Open", "General", "Allotted"],
            ["1000\n0", "52 310", "All India", "Govt Medical College, Ratlam", "BDS", "OBC", "OBC", "Allotted"]]
    found, check = nh.allotments(rows)
    # Tied ranks keep their number; numbers wrapped by narrow columns are joined again.
    assert found == [(1, "Open Seat Quota", "JIPMER PUDUCHERRY,Dhanvantari Nagar", "MBBS", "Open"), (52310, "All India", "Govt Medical College, Ratlam", "BDS", "OBC")]
    assert check["rows"] == 2 and not check["unreadable"]


def test_later_rounds_use_the_last_seven_cells_with_or_without_a_serial_column():
    earlier = ["All India", "A College", "MBBS", "Reported"]
    now = ["All India", "B College", "MBBS", "SC", "SC", "4", "Upgraded"]
    with_serial = ["7", "9344", *earlier, *now]                    # 13 cells: serial, rank, round 1, round 2
    without_serial = ["9344", *earlier, *earlier, *now]            # 16 cells: rank, rounds 1 and 2, round 3
    kept_seat = ["9345", *earlier, "-", "-", "-", "-", "-", "-", "Did not opt for upgradation"]
    found, check = nh.allotments([with_serial, without_serial, kept_seat])
    assert found == [(9344, "All India", "B College", "MBBS", "SC")] * 2
    assert check["no_seat_this_round"] == 1


def test_an_unknown_category_stops_the_load_count():
    _, check = nh.allotments([["1", "5", "All India", "X College", "MBBS", "Unknown", "General", "Allotted"]])
    assert check["unreadable"] == 1


def test_spellings_link_by_distinctive_words_and_pin_never_within_one_year():
    seen = {
        "Govt Medical College Ratlam,Gram Banjali, Sailana Road 457001": {"years": {2024, 2025}, "courses": {"MBBS"}},
        "Dr. LAXMINARAYAN PANDEY GOVT. MEDICAL COLLEGE, RATLAM,Gram Banjali 457001": {"years": {2026}, "courses": {"MBBS"}},
        "Government Medical College, Datia,Near 29th Battalion 475661": {"years": {2026}, "courses": {"MBBS"}},
        "Government Medical College, Datia,Near 29th Battalion 475661 Madhya Pradesh": {"years": {2025}, "courses": {"MBBS"}},
        # Generic words alone never link two colleges.
        "Government Medical College,gmc@x.com": {"years": {2023}, "courses": {"MBBS"}},
    }
    ids = nh.link_institutes(seen)
    names = list(seen)
    assert ids[names[0]] == ids[names[1]]
    assert ids[names[2]] == ids[names[3]]
    assert ids[names[0]] != ids[names[2]]
    assert ids[names[4]] not in (ids[names[0]], ids[names[2]])


def test_backtest_counts_whether_each_edge_held_the_next_year():
    closing = {"a|MBBS|allindia|Open": {2023: 1000, 2024: 1100, 2025: 1050}, "b|BDS|allindia|SC": {2023: 5000, 2024: 6000, 2025: 4000}}
    result = nh.backtest(closing, 2025)
    assert result["All seats"] == {"seats": 2, "safer": 50.0, "competitive": 0.0, "ambitious": 0.0}
    assert result["All India quota, Open, MBBS"]["safer"] == 100.0


def test_shortlist_seats_carry_a_band_from_their_history():
    r = route(seat("A College, Town", [1200, 1500, 1600, 9000]) + seat("B College, Town", [3000, 3200, 3300, None]))
    r["history"] = {
        "years": [2024, 2025, 2026],
        "institutes": {"acollegetown": "a", "bcollegetown": "b"},
        "closing": {"a|MBBS|allindia|Open": {"2024": 1500, "2025": 1700, "2026": 1600}, "b|MBBS|allindia|Open": {"2026": 3300}},
    }
    out = exam_routes.shortlist(r, 1300, "Open", "All India")
    by = {o["institute"]: o["history"] for o in out["options"]}
    assert by["A College, Town"]["band"] == "safer" and by["A College, Town"]["years"] == [2024, 2025, 2026]
    # One year of history gives no band, as on JEE.
    assert by["B College, Town"]["band"] is None
    # Without a history the shortlist is unchanged.
    del r["history"]
    assert all(o["history"] is None for o in exam_routes.shortlist(r, 1300, "Open", "All India")["options"])


def test_banded_seats_come_before_seats_beyond_the_recent_range():
    # C is the top-ranked college but only reached this rank in the stray round; its recent closing ranks are far away.
    r = route(seat("A College, Town", [5000, 5200, 5300, None]) + seat("C College, Town", [900, 1000, 1100, 9000]))
    r["records"][-1]["standing"] = 99
    r["history"] = {
        "years": [2024, 2025, 2026], "institutes": {"acollegetown": "a", "ccollegetown": "c"},
        "closing": {"a|MBBS|allindia|Open": {"2024": 5000, "2025": 5400, "2026": 5300}, "c|MBBS|allindia|Open": {"2024": 1000, "2025": 1200, "2026": 1100}},
    }
    out = exam_routes.shortlist(r, 4000, "Open", "All India")
    assert [o["institute"] for o in out["options"]] == ["A College, Town", "C College, Town"]
    assert out["options"][1]["history"]["band"] == "beyond"


def test_maharashtra_bands_use_the_merit_number_and_wait_for_it():
    rows = [{"institute": "X College", "programme": "Civil Engineering", "programme_code": "0100219110", "group": f"State Level, Stage I · {rnd}",
             "category": "GOPENS", "value": v, "second_value": m} for rnd, v, m in (("Round 1", 90.0, 30000), ("Round 2", 88.0, 34000))]
    r = route(rows, lower=False, rounds=["Round 1", "Round 2"])
    r["history"] = {"years": [2023, 2024, 2025], "uses": "second_value",
                    "closing": {"0100219110|State Level|GOPENS": {"2023": 30000, "2024": 36000, "2025": 34000}}}
    without = exam_routes.shortlist(r, 92.0, "GOPENS", "State Level, Stage I")["options"][0]["history"]
    assert without["band"] is None and without["needs"] == "merit"
    with_merit = exam_routes.shortlist(r, 92.0, "GOPENS", "State Level, Stage I", merit=20000)["options"][0]["history"]
    assert with_merit["band"] == "safer" and "merit number" in with_merit["explanation"] and "final-round" not in with_merit["explanation"]
    assert exam_routes.shortlist(r, 92.0, "GOPENS", "State Level, Stage I", merit=40000)["options"][0]["history"]["band"] == "ambitious"


def test_kea_seats_band_by_course_code_and_category():
    rows = [{"institute": "Mysore Medical College", "programme": "MBBS-GOVT.", "programme_code": "M002MG", "group": f"Karnataka quota · {rnd}",
             "category": "GM", "value": v} for rnd, v in (("Round 1", 9000), ("Round 2", 9461))]
    r = route(rows, rounds=["Round 1", "Round 2"])
    r["history"] = {"years": [2024, 2025, 2026], "key": "programme_code|category",
                    "closing": {"M002MG|GM": {"2024": 10755, "2025": 30129, "2026": 9461}}}
    band = exam_routes.shortlist(r, 8000, "GM", "Karnataka quota")["options"][0]["history"]
    assert band["band"] == "safer" and band["years"] == [2024, 2025, 2026]


def test_kea_rows_take_the_first_column_of_each_name_and_skip_other_courses(tmp_path, monkeypatch):
    from ingest import kea_history

    class Table:
        def __init__(self, rows): self.rows = rows
        def extract(self): return self.rows

    class Page:
        def __init__(self, rows): self.rows = rows
        def find_tables(self): return type("T", (), {"tables": [Table(self.rows)]})()
        def get_text(self): return "UGNEET -2024 MEDICAL MOP -UP ROUND FINAL SEAT ALLOTMENT LIST"

    header = ["SL.NO", "All India Rank", "Course Code", "Name", "Course Name", "Allotted Category", "Fee", "Status", "Course Code", "Allotted Category"]
    pages = [Page([header, ["1", "17002", "M003MG", "KIMS", "MBBS-GOVT.", "GM", "1", "Allotted", "M009MG", "2AG"],
                   ["2", "5000", "I719AG", "SDM Ayurveda", "BAMS-GOVT", "GM", "1", "Allotted", "-", "-"]])]

    class Doc(list):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(kea_history.pymupdf, "open", lambda path: Doc(pages))
    pdf = tmp_path / "round3-med.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    found = kea_history.read_file(pdf)
    assert found["allotments"] == [[17002, "M003MG", "GM"]]
    assert kea_history.ROUND_TITLE["round3"].search(found["title"])
