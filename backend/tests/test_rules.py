"""Unit tests for pure rules. Numbers below are constructed inputs, not real statistics."""
import pytest

from app.services.bands import CutoffPoint, classify
from app.services.branches import branch_family, required_paper
from app.services.eligibility import Student, StudentRanks, class12_threshold, gender_pools, quota_applies, rank_list_name, seat_claims
from app.services.scoring import FitInputs, PlacementEvidence, career_score, percentile_of, quality_score, reputation_score, suitability_score
from ingest.josaa_parse import SourceFormatError, parse_programme, parse_rank, parse_table


def student(**kw):
    return Student(**{"category": "GEN", "gender": "male", "is_pwd": False, "eligibility_state": "Kerala", **kw})


def test_general_candidate_claims_only_open_on_crl():
    claims = seat_claims(student(main=StudentRanks(crl=100)), "JEE_MAIN")
    assert [(c.seat_type, c.rank, c.rank_list) for c in claims] == [("OPEN", 100, "JEE_MAIN:CRL")]


def test_category_rank_is_never_used_for_open_seats_and_crl_never_for_category_seats():
    claims = {c.seat_type: c for c in seat_claims(student(category="OBC-NCL", main=StudentRanks(crl=50000, category_rank=9000)), "JEE_MAIN")}
    assert claims["OPEN"].rank == 50000 and claims["OPEN"].rank_list == "JEE_MAIN:CRL"
    assert claims["OBC-NCL"].rank == 9000 and claims["OBC-NCL"].rank_list == "JEE_MAIN:OBC-NCL"


def test_missing_category_rank_creates_no_claim_and_is_not_guessed_from_crl():
    claims = seat_claims(student(category="SC", main=StudentRanks(crl=50000)), "JEE_MAIN")
    assert [c.seat_type for c in claims] == ["OPEN"]


@pytest.mark.parametrize("category,seat", [("GEN-EWS", "EWS"), ("OBC-NCL", "OBC-NCL"), ("SC", "SC"), ("ST", "ST")])
def test_pwd_seats_use_pwd_lists(category, seat):
    ranks = StudentRanks(crl=9000, category_rank=800, crl_pwd=70, category_pwd_rank=7)
    claims = {c.seat_type: c for c in seat_claims(student(category=category, is_pwd=True, main=ranks), "JEE_MAIN")}
    assert set(claims) == {"OPEN", "OPEN-PwD", seat, f"{seat}-PwD"}
    assert claims["OPEN-PwD"].rank == 70 and claims[f"{seat}-PwD"].rank == 7


def test_pwd_seats_not_available_without_pwd_status():
    claims = seat_claims(student(main=StudentRanks(crl=100, crl_pwd=5)), "JEE_MAIN")
    assert [c.seat_type for c in claims] == ["OPEN"]


def test_advanced_rank_requires_qualification():
    s = student(advanced=StudentRanks(crl=100))
    assert seat_claims(s, "JEE_ADVANCED") == []
    assert seat_claims(student(advanced=StudentRanks(crl=100), advanced_qualified=True), "JEE_ADVANCED")[0].rank_list == "JEE_ADVANCED:CRL"


def test_main_and_advanced_ranks_are_on_different_lists():
    assert rank_list_name("JEE_MAIN", "OPEN") != rank_list_name("JEE_ADVANCED", "OPEN")


def test_only_female_candidates_get_female_pool():
    assert gender_pools(student(gender="female")) == ["neutral", "female"]
    assert gender_pools(student(gender="male")) == ["neutral"]
    assert gender_pools(student(gender="other")) == ["neutral"]


HOME = {"HS": {"Karnataka"}}


def test_home_state_quota_uses_class12_state():
    assert quota_applies("HS", "Karnataka", "NIT", HOME)[0] is True
    assert quota_applies("OS", "Karnataka", "NIT", HOME)[0] is False


def test_other_state_quota_for_outside_candidates():
    assert quota_applies("HS", "Kerala", "NIT", HOME)[0] is False
    assert quota_applies("OS", "Kerala", "NIT", HOME)[0] is True


def test_iits_never_use_state_quotas():
    assert quota_applies("AI", "Kerala", "IIT", {})[0] is True
    assert quota_applies("HS", "Kerala", "IIT", {"HS": {"Kerala"}})[0] is False


def test_goa_special_quota_rules():
    rules = {"GO": {"Goa"}, "HS": {"Daman and Diu", "Dadra and Nagar Haveli", "Lakshadweep"}}
    assert quota_applies("GO", "Goa", "NIT", rules)[0] is True
    assert quota_applies("HS", "Goa", "NIT", rules)[0] is False
    assert quota_applies("OS", "Goa", "NIT", rules)[0] is False
    assert quota_applies("HS", "Lakshadweep", "NIT", rules)[0] is True
    assert quota_applies("OS", "Lakshadweep", "NIT", rules)[0] is False
    assert quota_applies("OS", "Kerala", "NIT", rules)[0] is True


def test_srinagar_jk_and_ladakh_quotas():
    rules = {"JK": {"Jammu and Kashmir"}, "LA": {"Ladakh"}}
    assert quota_applies("JK", "Jammu and Kashmir", "NIT", rules)[0] is True
    assert quota_applies("LA", "Jammu and Kashmir", "NIT", rules)[0] is False
    assert quota_applies("LA", "Ladakh", "NIT", rules)[0] is True
    assert quota_applies("OS", "Ladakh", "NIT", rules)[0] is False


def test_other_state_is_undecided_when_home_states_are_unrecorded():
    applies, reason = quota_applies("OS", "Kerala", "NIT", {})
    assert applies is False and "not recorded" in reason


def test_class12_thresholds():
    assert class12_threshold(student()) == 75
    assert class12_threshold(student(category="SC")) == 65
    assert class12_threshold(student(is_pwd=True)) == 65


HISTORY = [CutoffPoint(2024, 1000), CutoffPoint(2025, 1200), CutoffPoint(2026, 1100)]


@pytest.mark.parametrize("rank,band", [(900, "safer"), (901, "competitive"), (1200, "competitive"), (1201, "ambitious"), (1440, "ambitious"), (1441, "beyond")])
def test_band_boundaries(rank, band):
    assert classify(rank, HISTORY, 2026).band == band


def test_band_has_no_probability_field():
    fields = vars(classify(900, HISTORY, 2026))
    assert not any("prob" in name or "chance" in name for name in fields)


def test_band_needs_two_recent_years():
    result = classify(100, [CutoffPoint(2026, 1000)], 2026)
    assert result.band is None and "1 year" in result.explanation


def test_old_years_are_ignored():
    result = classify(100, [CutoffPoint(2020, 1000), CutoffPoint(2021, 1000), CutoffPoint(2026, 1000)], 2026)
    assert result.band is None


def test_parse_rank_marks_preparatory():
    assert parse_rank("50P") == (50, True)
    assert parse_rank("1234") == (1234, False)
    assert parse_rank("1234.0") == (1234, False)
    assert parse_rank("") == (None, False)


def test_parse_programme():
    assert parse_programme("Civil Engineering (4 Years, Bachelor of Technology)") == ("Civil Engineering", 4, "Bachelor of Technology")
    assert parse_programme("CSE (5 Years, Bachelor and Master of Technology (Dual Degree))") == ("CSE", 5, "Bachelor and Master of Technology (Dual Degree)")


def test_parser_rejects_changed_source_layout():
    with pytest.raises(SourceFormatError):
        parse_table("<table><tr><th>Something</th><th>Else</th></tr></table>")


@pytest.mark.parametrize("name,family", [
    ("Computer Science and Engineering", "CS"), ("Information Technology", "CS"), ("Mathematics and Computing", "MATH_COMP"),
    ("Electrical and Electronics Engineering", "EE"), ("Electronics and Communication Engineering", "ECE"),
    ("Artificial Intelligence and Data Science", "AI_DS"), ("Civil Engineering", "CIVIL"),
    ("Ocean Engineering and Naval Architecture", "OCEAN"), ("Architecture", "ARCH"), ("Materials Science and Engineering", "MATERIALS"),
])
def test_branch_families(name, family):
    assert branch_family(name) == family


def test_required_paper_separates_architecture_and_planning():
    assert required_paper("NIT", "Bachelor of Technology", "CSE") == "main_paper1"
    assert required_paper("NIT", "Bachelor of Architecture", "Architecture") == "main_paper2a"
    assert required_paper("GFTI", "Bachelor of Planning", "Planning") == "main_paper2b"
    assert required_paper("IIT", "Bachelor of Technology", "CSE") == "advanced"


def test_missing_rank_is_no_evidence_not_a_low_score():
    assert reputation_score(None) is None
    assert reputation_score(1) == 100


def test_quality_is_withheld_when_evidence_is_thin():
    result = quality_score(5, "note", (None, "Data not available", 0.0))
    assert result.score is None and result.status == "insufficient_evidence"
    assert {c.key for c in result.components if c.score is None} >= {"career_outcomes", "academic_faculty"}


def test_quality_appears_only_with_enough_coverage():
    with_programme = quality_score(5, "note", (80.0, "programme", 1.0))
    assert with_programme.coverage == 0.35 and with_programme.score is None


COHORT = {2025: [500000.0, 800000.0, 1200000.0, 2000000.0]}


def test_highest_package_is_not_used_for_career_score():
    assert not hasattr(PlacementEvidence("programme", 1, 1, 1, 2025), "highest_salary_inr")


def test_institute_wide_placements_get_half_coverage_and_label():
    records = [PlacementEvidence("institution", 1200000, 100, 80, 2025)]
    score, note, factor = career_score(records, COHORT, min_cohort=2)
    assert factor == 0.5 and "institute-wide" in note and score is not None


def test_programme_placements_win_over_institute_wide():
    records = [PlacementEvidence("institution", 2000000, 100, 100, 2025), PlacementEvidence("programme", 500000, 100, 50, 2025)]
    score, note, factor = career_score(records, COHORT, min_cohort=2)
    assert factor == 1.0 and "programme-level" in note and score < 60


def test_no_placements_produces_no_score():
    assert career_score([], COHORT) == (None, "Data not available", 0.0)


def fit(**kw):
    return suitability_score(FitInputs(**{
        "branch_family": "CS", "institute_type": "NIT", "state": "Kerala", "nirf_rank": None, "career_dimension_score": None, "annual_cost_inr": None, **kw,
    }))


def test_unknown_dimensions_are_neutral():
    result = fit()
    assert result.score == 50.0 and result.coverage == 0.0
    assert all(c.score is None for c in result.components)


def test_preference_changes_score():
    assert fit(preferred_branches=frozenset({"CS"})).score > fit(preferred_branches=frozenset({"ECE"})).score


def test_changing_priorities_changes_score():
    base = {"branch_fit": 10, "reputation": 90}
    other = {"branch_fit": 90, "reputation": 10}
    kw = {"preferred_branches": frozenset({"ECE"}), "nirf_rank": 2}
    assert fit(priorities=base, **kw).score > fit(priorities=other, **kw).score


def test_suitability_is_reproducible():
    kw = {"preferred_branches": frozenset({"CS"}), "nirf_rank": 20}
    assert fit(**kw) == fit(**kw)


def test_zero_priorities_gives_no_score():
    assert fit(priorities={k: 0 for k in ("branch_fit", "reputation")}).status == "no_priorities"


def test_no_placement_score_until_cohort_is_broad_enough():
    records = [PlacementEvidence("institution", 1200000, 100, 80, 2025)]
    score, note, factor = career_score(records, {2025: [1200000.0] * 18})
    assert score is None and factor == 0.0 and "not scored" in note and "18" in note


def test_nirf_figures_are_not_treated_as_a_placement_rate():
    # NIRF counts students graduating in minimum time, which is not the eligible group.
    records = [PlacementEvidence("institution", 1200000, None, 80, 2025, "nirf_graduation_outcomes")]
    assert career_score(records, COHORT, min_cohort=2)[0] == percentile_of(1200000, COHORT[2025])


def test_affordability_is_not_scored_from_a_missing_cost():
    result = fit(annual_budget_inr=300000)
    assert next(c for c in result.components if c.key == "affordability").score is None


def test_median_words_catch_a_mismatch_and_tolerate_misspellings():
    from ingest.nirf_pdf import OutcomeRow, sanity_problems, words_to_number
    assert words_to_number("2050000(Tenty Lakh Fifty Thousand)") == 2050000
    assert words_to_number("1250000(RUPEES TWELEVE LAKH FIFTY THOUSAND ONLY)") == 1250000
    assert words_to_number("1696000(Sixteen Lakhs Ninety Six Thousand)") == 1696000
    assert words_to_number("1700000") is None
    row = OutcomeRow(2025, "2024-25", None, None, 100, 80, 1700000, "1700000(Seven Lakh)", 5, 1)
    assert any("disagree" in p for p in sanity_problems(row))


def test_nit_names_are_not_fuzzy_matched():
    from ingest.nirf_fetch import name_matches
    names = {"nit-goa": ["National Institute of Technology Goa"], "nit-patna": ["National Institute of Technology Patna"]}
    assert name_matches("NationalInstituteofTechnologyGoa", "nit-goa", names, {})
    assert not name_matches("NationalInstituteofTechnologyPatna", "nit-goa", names, {})
    assert not name_matches(None, "nit-goa", names, {})
    assert name_matches("Bespoke Name", "nit-goa", names, {"nit-goa": ["Bespoke Name"]})


def test_salaries_are_compared_only_within_a_graduating_year():
    cohorts = {2023: [1000000.0, 2000000.0], 2024: [3000000.0, 4000000.0]}
    records = [PlacementEvidence("institution", 2000000, None, 80, 2023, "nirf_graduation_outcomes")]
    # Top of its own year, even though it would be the bottom of the following one.
    assert career_score(records, cohorts, min_cohort=2)[0] == 100.0


def test_years_without_a_broad_cohort_are_left_out():
    cohorts = {2024: [1000000.0, 3000000.0], 2025: [500000.0]}
    records = [
        PlacementEvidence("institution", 1000000, None, 80, 2024, "nirf_graduation_outcomes"),
        PlacementEvidence("institution", 9000000, None, 80, 2025, "nirf_graduation_outcomes"),
    ]
    score, note, _ = career_score(records, cohorts, min_cohort=2)
    assert score == 50.0 and "2024" in note and "2025" not in note


def test_tiny_graduating_classes_are_shown_but_not_scored():
    cohorts = {2024: [1000000.0, 3000000.0]}
    records = [PlacementEvidence("institution", 3000000, None, 40, 2024, "nirf_graduation_outcomes", 73)]
    score, note, factor = career_score(records, cohorts, min_cohort=2)
    assert score is None and factor == 0.0 and "too uncertain" in note


def test_career_note_states_the_comparison():
    records = [PlacementEvidence("institution", 3000000, None, 300, 2024, "nirf_graduation_outcomes", 400)]
    assert "100% of 2+" in career_score(records, {2024: [1000000.0, 3000000.0]}, min_cohort=2)[1]
