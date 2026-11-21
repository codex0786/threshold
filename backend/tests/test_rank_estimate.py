"""The rank estimator gives a range that brackets NTA's own published points."""
from app.services.rank_estimate import YEARS, calibration_ratios, estimate


def test_each_published_year_falls_inside_its_own_range():
    for y in YEARS:
        result = estimate(y.ur_cutoff_percentile, y.year)
        assert result["rank_low"] <= y.ur_qualified <= result["rank_high"], y.year


def test_ratios_are_close_to_one():
    assert all(0.9 < r < 1.1 for r in calibration_ratios())


def test_future_year_range_is_wider_and_never_below_the_latest_count():
    latest = max(YEARS, key=lambda y: y.year)
    now = estimate(95.0, latest.year)
    later = estimate(95.0, latest.year + 1)
    assert later["rank_low"] == now["rank_low"]
    assert later["rank_high"] > now["rank_high"]


def test_higher_percentile_never_gives_a_worse_rank():
    previous = None
    for p in (60, 80, 90, 95, 98, 99, 99.5, 99.9):
        r = estimate(p, 2027)
        assert r["rank_low"] <= r["rank_high"]
        if previous:
            assert r["rank_high"] <= previous["rank_high"]
        previous = r


def test_top_percentile_is_rank_one_and_low_percentile_warns():
    assert estimate(100, 2027)["rank_low"] == 1
    assert estimate(70, 2027)["warnings"]


def test_endpoint_validates_and_stores_nothing(client):
    ok = client.post("/api/v1/estimates/rank", json={"percentile": 97.5, "exam_year": 2027})
    assert ok.status_code == 200 and ok.json()["rank_list"] == "JEE_MAIN:CRL"
    assert client.post("/api/v1/estimates/rank", json={"percentile": 101}).status_code == 422
