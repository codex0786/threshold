"""Readings of NIRF submissions outside Engineering, and the institute profiles built from them."""
from ingest.nirf_programme import text_rows
from ingest.exam_profiles import institutes_matching
import pytest

HEADING = "UG [5 Years Program(s)]: Placement"
TEXT = """UG [3 Years Program(s)]: Placement & higher studies for previous 3 years
2020-21
0
0
2021-22
0
2022-23
0
0
0(Zero)
0
UG [5 Years Program(s)]: Placement & higher studies for previous 3 years
Academic Year
2018-19
180
179
2019-20
0
2022-23
177
87
1450000(Fourteen
Lakhs and Fifty
Thousand)
11
2019-20
180
179
2020-21
0
2023-24
158
77
1400000(Fourteen
Lakh Only)
10
PG [1 Years Program(s)]: Placement & higher studies for previous 3 years
2022-23
50
50
2022-23
42
27
700000(Seven Lakh
Only)
6
"""


def test_text_reading_takes_only_the_named_programme_and_joins_wrapped_medians():
    rows = text_rows(TEXT, HEADING)
    assert [(r.academic_year, r.graduating_students, r.students_placed, r.median_salary_inr, r.higher_studies_students) for r in rows] == [
        ("2022-23", 177, 87, 1450000, 11), ("2023-24", 158, 77, 1400000, 10)]
    assert rows[0].median_salary_raw == "1450000(Fourteen Lakhs and Fifty Thousand)"


def test_missing_programme_reads_nothing():
    assert text_rows(TEXT, "UG [4 Years Program(s)]: Placement") == []


def test_registry_entries_must_match_an_institute():
    route = {"code": "clat", "records": [{"institute": "Chanakya National Law University (CNLU), Patna"}]}
    assert institutes_matching(route, "Chanakya National Law University (CNLU)") == ["Chanakya National Law University (CNLU), Patna"]
    with pytest.raises(SystemExit):
        institutes_matching(route, "Chanakya Law School")
