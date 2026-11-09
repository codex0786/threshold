from app.services.exam_routes import add_standing, invalid_value, query, summary

RANK = {"metric": {"lower_is_better": True}, "records": [
    {"institute": "A", "programme": "Law", "group": "V", "category": "General", "value": 120},
    {"institute": "B", "programme": "Law", "group": "V", "category": "General", "value": 500},
    {"institute": "A", "programme": "Law", "group": "H", "category": "Women", "value": None},
]}
SCORE = {"metric": {"lower_is_better": False}, "records": [
    {"institute": "A", "programme": "CSE", "group": "R1", "category": "OPEN", "value": 700},
    {"institute": "B", "programme": "Civil", "group": "R1", "category": "OPEN", "value": 400},
]}


def test_rank_matches_closing_ranks_at_or_beyond_the_student():
    result = query(RANK, value=300, category="General")
    assert [r["institute"] for r in result["records"]] == ["B"]
    assert query(RANK, value=120, category="General")["matched"] == 2


def test_score_matches_closing_scores_at_or_below_the_student():
    assert [r["programme"] for r in query(SCORE, value=500, category="OPEN")["records"]] == ["Civil"]


def test_a_figure_is_never_compared_across_categories():
    result = query(RANK, value=300)
    assert result["compared"] is False and result["matched"] == 2
    assert query(RANK, value=300, category="General")["compared"] is True


def test_closest_order_puts_the_strongest_past_outcome_first():
    assert [r["institute"] for r in query(RANK, order="closest")["records"]] == ["A", "B"]
    assert [r["institute"] for r in query(SCORE, order="closest")["records"]] == ["A", "B"]


def test_missing_cutoff_is_reported_and_never_treated_as_a_number():
    result = query(RANK, value=1)
    assert result["total"] == 2 and result["matched"] == 2
    assert [r["category"] for r in result["no_figure"]] == ["Women"]
    assert query(RANK, value=1, category="Women")["matched"] == 0


def test_filters_narrow_the_records():
    assert query(RANK, category="Women")["no_figure"][0]["group"] == "H"
    assert query(SCORE, search="civ")["matched"] == 1
    assert query(RANK, group="V")["total"] == 2


def test_summary_omits_records():
    result = summary({**RANK, "code": "x"})
    assert "records" not in result and result["record_count"] == 3 and result["institute_count"] == 2


def test_a_route_with_restricted_quotas_needs_a_quota_before_comparing():
    route = {"compare_requires_group": True, **RANK}
    assert query(route, value=300, category="General")["missing"] == ["quota"]
    assert query(route, value=300, category="General")["compared"] is False
    assert query(route, value=300)["missing"] == ["category", "quota"]
    assert query(route, value=300, category="General", group="V")["compared"] is True


def test_a_student_sees_only_the_chosen_quota():
    route = {"compare_requires_group": True, "metric": {"lower_is_better": True}, "records": [
        {"institute": "A", "programme": "MBBS", "group": "All India", "category": "Open", "value": 28000},
        {"institute": "B", "programme": "MBBS", "group": "NRI", "category": "Open", "value": 90000},
    ]}
    assert query(route, value=50000, category="Open", group="All India")["matched"] == 0
    assert query(route, value=50000, category="Open", group="NRI")["matched"] == 1


def test_figures_outside_the_scale_are_refused():
    percentile = {"metric": {"label": "Percentile", "max": 100}}
    rank = {"metric": {"label": "Rank", "whole_number": True}}
    assert invalid_value(percentile, 150) and invalid_value(rank, 1.5)
    assert invalid_value(percentile, 100) is None and invalid_value(rank, 2) is None


def test_course_filter_keeps_courses_apart():
    route = {"metric": {"lower_is_better": True}, "records": [
        {"institute": "A", "programme": "MBBS", "group": "All India", "category": "Open", "value": 20000},
        {"institute": "A", "programme": "BDS", "group": "All India", "category": "Open", "value": 90000},
    ]}
    assert [r["programme"] for r in query(route, programme="BDS")["records"]] == ["BDS"]
    assert summary(route)["programmes"] == ["BDS", "MBBS"]


def test_exam_routes_api_refuses_figures_outside_the_scale(client):
    assert client.get("/api/v1/exams").status_code == 200
    assert client.get("/api/v1/exams/not-a-route").status_code == 404


def test_top_order_puts_ranked_institutes_first_then_contested_seats():
    route = {"metric": {"lower_is_better": True}, "records": [
        {"institute": "Unranked", "programme": "MBBS", "group": "All India", "category": "Open", "value": 3000},
        {"institute": "Ranked", "programme": "MBBS", "group": "All India", "category": "Open", "value": 9000, "ranking": {"rank": 5}},
        {"institute": "Ranked lower", "programme": "MBBS", "group": "All India", "category": "Open", "value": 6000, "ranking": {"rank": 40}},
    ]}
    add_standing(route)
    assert [r["institute"] for r in query(route)["records"]] == ["Ranked", "Ranked lower", "Unranked"]
    assert [r["institute"] for r in query(route, order="closest")["records"]] == ["Unranked", "Ranked lower", "Ranked"]


def test_contest_compares_only_within_the_same_course_category_and_quota():
    route = {"metric": {"lower_is_better": True}, "records": [
        {"institute": "A", "programme": "MBBS", "group": "All India", "category": "Open", "value": 1000},
        {"institute": "B", "programme": "MBBS", "group": "All India", "category": "SC", "value": 90000},
    ]}
    add_standing(route)
    assert route["records"][0]["standing"] == route["records"][1]["standing"]


def test_an_empty_list_reports_how_far_it_went_and_which_quotas_reached_the_student():
    route = {"compare_requires_group": True, "metric": {"lower_is_better": True}, "records": [
        {"institute": "A", "programme": "MBBS", "group": "All India", "category": "Open", "value": 28000},
        {"institute": "B", "programme": "MBBS", "group": "Deemed", "category": "Open", "value": 90000},
        {"institute": "C", "programme": "MBBS", "group": "Deemed", "category": "SC", "value": 95000},
    ]}
    result = query(route, value=50000, category="Open", group="All India", programme="MBBS")
    assert result["matched"] == 0 and result["furthest"] == 28000
    assert result["elsewhere"] == [{"group": "Deemed", "count": 1}]


def test_a_combined_list_joins_quotas_open_to_the_same_candidates():
    route = {"compare_requires_group": True, "combined_quotas": {"All open": ["All India", "Open Seat Quota"]}, "metric": {"lower_is_better": True}, "records": [
        {"institute": "KGMU", "programme": "MBBS", "group": "All India · Round 3", "category": "Open", "value": 2500, "ranking": {"rank": 8}},
        {"institute": "AIIMS Jodhpur", "programme": "MBBS", "group": "Open Seat Quota · Round 3", "category": "Open", "value": 300, "ranking": {"rank": 19}},
        {"institute": "Private", "programme": "MBBS", "group": "Self-Financed Merit Seat · Round 3", "category": "Open", "value": 90000},
    ]}
    add_standing(route)
    assert summary(route)["groups"][0] == "All open · Round 3"
    result = query(route, value=200, category="Open", group="All open · Round 3")
    assert {r["institute"] for r in result["records"]} == {"KGMU", "AIIMS Jodhpur"}
    assert result["elsewhere"] == [{"group": "Self-Financed Merit Seat · Round 3", "count": 1}]


def test_quotas_shown_together_are_scored_together():
    route = {"combined_quotas": {"All open": ["All India", "Open Seat Quota"]}, "metric": {"lower_is_better": True}, "records": [
        {"institute": "KGMU", "programme": "MBBS", "group": "All India · Round 3", "category": "Open", "value": 2500, "ranking": {"rank": 8}},
        {"institute": "Other", "programme": "MBBS", "group": "All India · Round 3", "category": "Open", "value": 9000},
        {"institute": "JIPMER", "programme": "MBBS", "group": "Open Seat Quota · Round 3", "category": "Open", "value": 400, "ranking": {"rank": 4}},
        {"institute": "AIIMS", "programme": "MBBS", "group": "Open Seat Quota · Round 3", "category": "Open", "value": 300, "ranking": {"rank": 19}},
    ]}
    add_standing(route)
    # Scored per quota, the Open Seat Quota seats would only be compared with each other and drop below KGMU.
    order = [r["institute"] for r in query(route, value=100, category="Open", group="All open · Round 3")["records"]]
    assert order.index("JIPMER") < order.index("KGMU") and order.index("AIIMS") < order.index("KGMU")


def test_female_only_seats_are_hidden_for_male_and_other_students_only():
    route = {"compare_requires_group": True, "metric": {"lower_is_better": True}, "records": [
        {"institute": "LHMC (Female Seat only )", "programme": "MBBS", "group": "All India", "category": "Open", "value": 900, "female_only": True},
        {"institute": "MAMC", "programme": "MBBS", "group": "All India", "category": "Open", "value": 800},
        {"institute": "Women's college (Female Seat only )", "programme": "MBBS", "group": "Deemed", "category": "Open", "value": 90000, "female_only": True},
    ]}
    def names(gender):
        return [r["institute"] for r in query(route, value=500, category="Open", group="All India", gender=gender)["records"]]
    assert set(names("female")) == set(names(None)) == {"MAMC", "LHMC (Female Seat only )"}
    assert names("male") == names("other") == ["MAMC"]
    assert query(route, value=50000, category="Open", group="All India", gender="male")["elsewhere"] == []
    assert query(route, value=50000, category="Open", group="All India", gender="female")["elsewhere"] == [{"group": "Deemed", "count": 1}]
    assert query(route, gender="male")["hidden_female_only"] == 2


def test_extraction_flags_female_only_seats_from_mccs_marker():
    from ingest.exam_extract import last_ranks
    records = last_ranks({("Lady Hardinge Medical College, New Delhi (Female Seat only )", "MBBS", "All India", "Open"): [900],
                          ("Government Medical College, Sircilla, near Kasturba Girls School", "MBBS", "All India", "Open"): [20000]}, "Round 3")
    assert [r["female_only"] for r in records] == [True, False]
