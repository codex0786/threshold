"""GATE (CCMT) history: score bands, seat keys across years, and the backtest."""
import json

from app.services.bands import SCORE_MARGIN, CutoffPoint, classify_score
from app.services.exam_routes import ccmt_seat_key, seat_band
from ingest import ccmt_history


def points(*pairs):
    return [CutoffPoint(year, score) for year, score in pairs]


def test_score_bands_follow_the_margin():
    history = points((2024, 400), (2025, 420), (2026, 410))
    assert classify_score(420 + SCORE_MARGIN, history, 2026).band == "safer"
    assert classify_score(420 + SCORE_MARGIN - 1, history, 2026).band == "competitive"
    assert classify_score(400, history, 2026).band == "competitive"
    assert classify_score(399, history, 2026).band == "ambitious"
    assert classify_score(400 - SCORE_MARGIN, history, 2026).band == "ambitious"
    assert classify_score(400 - SCORE_MARGIN - 1, history, 2026).band == "beyond"


def test_one_year_gives_no_band_unless_far_below():
    assert classify_score(500, points((2026, 450)), 2026).band is None
    assert classify_score(300, points((2026, 450)), 2026).band == "beyond"


def test_seat_key_ignores_spacing_punctuation_and_group_spelling():
    a = ccmt_seat_key("National Institute of Technology  Agartala", "Computer Science & Engineering", "G1", "OPEN")
    b = ccmt_seat_key("National Institute of Technology Agartala", "Computer Science and Engineering".replace(" and ", " & "), "Group 1 · Round 2", "OPEN ")
    assert a == b
    assert ccmt_seat_key("Shri Mata Vaishno Devi University, Katra, J&K", "X", "G1", "SC") == ccmt_seat_key("Shri Mata Vaishno Devi University, Katra", "X", "Group 1", "SC")


def test_history_uses_the_lowest_main_round_score(tmp_path):
    rows = [
        ["Round 1", "NIT A", "CSE", "G1", "OPEN", "800", "600"],
        ["Round 3", "NIT A", "CSE", "G1", "OPEN", "590", "580"],
        ["National Spot Round", "NIT A", "CSE", "Group 1", "OPEN", "500", "400"],
    ]
    path = tmp_path / "ccmt-2026-orcr-from-page.json"
    path.write_text(json.dumps({"total": 3, "header": [], "rows": rows}))
    closing, check = ccmt_history.closing_scores({2026: path})
    assert closing[ccmt_seat_key("NIT A", "CSE", "G1", "OPEN")] == {2026: 580}
    assert check["2026"] == {"rows": 3, "main_round_rows": 2}


def test_backtest_counts_the_safer_edge():
    key = ccmt_seat_key("NIT A", "CSE", "G1", "OPEN")
    held = {key: {2023: 500, 2024: 520, 2025: 520 + SCORE_MARGIN}}
    broke = {key: {2023: 500, 2024: 520, 2025: 520 + SCORE_MARGIN + 1}}
    assert ccmt_history.backtest(held, 2025)["All seats"]["safer"] == 100.0
    assert ccmt_history.backtest(broke, 2025)["All seats"]["safer"] == 0.0
    assert "Group 1, OPEN" in ccmt_history.backtest(held, 2025)


def test_seat_band_reads_gate_history():
    key = ccmt_seat_key("NIT A", "CSE", "G1", "OPEN")
    route = {"metric": {"lower_is_better": False}, "history": {"key": "institute|programme|group|category", "years": [2024, 2025, 2026], "margin": SCORE_MARGIN,
                                                                  "closing": {key: {"2024": 600, "2025": 610, "2026": 620}}}}
    row = {"institute": "NIT A", "programme": "CSE", "group": "Group 1 · Round 1", "category": "OPEN"}
    assert seat_band(route, row, 700)["band"] == "safer"
    assert seat_band(route, row, 560)["band"] == "ambitious"
