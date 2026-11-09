from ingest.nirf_official import confirm

OFFICIAL = {
    "ranks": [[9, "IR-E-U-0467", "National Institute of Technology Tiruchirappalli"], [10, "IR-E-U-0701", "Indian Institute of Technology (Banaras Hindu University) Varanasi"]],
    "reviewed_matches": {"iit-bhu": "IR-E-U-0701"},
}


def test_a_rank_is_confirmed_only_by_the_same_name_or_a_reviewed_match_at_that_rank():
    assert confirm(OFFICIAL, "nit-tiruchirappalli", "National Institute of Technology, Tiruchirappalli", 9) == "IR-E-U-0467"
    assert confirm(OFFICIAL, "iit-bhu", "Indian Institute of Technology (BHU) Varanasi", 10) == "IR-E-U-0701"
    assert confirm(OFFICIAL, "iit-bhu", "Indian Institute of Technology (BHU) Varanasi", 9) is None
    assert confirm(OFFICIAL, "nit-trichy-typo", "National Institute of Technology Trichy", 9) is None
