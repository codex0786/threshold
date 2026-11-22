"""KCET (KEA UGCET) engineering: course names, the 2024 code mapping and short college names."""
from ingest.kcet import CODES_2024, course_name, rejoin_words, short_name, squash


def test_course_names_read_naturally():
    assert course_name("COMPUTER SCIENCE AND ENGINEERING(DA TA SCIENCE)") == "Computer Science and Engineering(Data Science)"
    assert course_name("ELECTRONICS AND COMMUNICATION ENGG") == "Electronics and Communication Engg."


def test_2024_codes_point_at_current_course_keys():
    assert CODES_2024["CS"] == squash("COMPUTER SCIENCE AND ENGINEERING")
    assert CODES_2024["DS"] == squash("COMPUTER SCIENCE AND ENGINEERING(DA TA SCIENCE)")
    assert CODES_2024["EE"] == squash("ELECTRICAL & ELECTRONICS ENGINEERING")
    assert "AI" not in CODES_2024  # "Artificial Intelligence" could be either of two current courses


def test_short_college_name():
    assert short_name("B M S College of Engineering, Basavanagudi, Bangalore (AUTONOMOUS) POST BOX") == "B M S College of Engineering"


def test_words_kea_split_across_lines_are_rejoined():
    names = {"Electronics and Telecommunica Tion Engineering", "Electronics and Telecommunication Engineering",
             "Computer Science and Engineering(Da Ta Science)", "Data Science"}
    fixed = rejoin_words(names)
    assert fixed["Electronics and Telecommunica Tion Engineering"] == "Electronics and Telecommunication Engineering"
    assert fixed["Computer Science and Engineering(Da Ta Science)"] == "Computer Science and Engineering (Data Science)"
    assert fixed["Data Science"] == "Data Science"
