"""JoSAA seat eligibility. Pure functions with no database access.

Authority: JoSAA 2026 Business Rules, clauses 2, 5, 8, 11, 12 and the seat allotment
sequences. A seat is only ever matched against the rank list it is allocated on, so a
candidate's CRL can never be compared with a category closing rank, or the reverse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Category = Literal["GEN", "GEN-EWS", "OBC-NCL", "SC", "ST"]
Gender = Literal["female", "male", "other"]
Exam = Literal["JEE_MAIN", "JEE_ADVANCED"]

_CATEGORY_SEAT = {"GEN-EWS": "EWS", "OBC-NCL": "OBC-NCL", "SC": "SC", "ST": "ST"}
ADVANCED_TYPES = {"IIT", "IISC"}


@dataclass(frozen=True)
class StudentRanks:
    """Each value is the rank on one specific published list. CRL is held apart from category ranks."""

    crl: int | None = None
    category_rank: int | None = None
    crl_pwd: int | None = None
    category_pwd_rank: int | None = None


@dataclass(frozen=True)
class Student:
    category: Category
    gender: Gender
    is_pwd: bool
    # State where Class XII was FIRST attempted (clause 8). Not residence and not native place.
    eligibility_state: str | None
    main: StudentRanks = field(default_factory=StudentRanks)
    advanced: StudentRanks = field(default_factory=StudentRanks)
    advanced_qualified: bool = False


@dataclass(frozen=True)
class SeatClaim:
    """A seat type the student can compete for, and the rank that applies to it."""

    seat_type: str
    rank: int
    rank_list: str


def exam_for(institute_type: str) -> Exam:
    return "JEE_ADVANCED" if institute_type in ADVANCED_TYPES else "JEE_MAIN"


def rank_list_name(exam: Exam, seat_type: str) -> str:
    """Name the published list a seat type is allocated on, e.g. JEE_MAIN:OBC-NCL."""
    names = {"OPEN": "CRL", "OPEN-PwD": "CRL-PwD"}
    return f"{exam}:{names.get(seat_type, seat_type)}"


def seat_claims(student: Student, exam: Exam) -> list[SeatClaim]:
    """Seat types open to this student for an exam. Missing ranks produce no claim, never a guess."""
    if exam == "JEE_ADVANCED" and not student.advanced_qualified:
        return []
    ranks = student.advanced if exam == "JEE_ADVANCED" else student.main
    candidates: list[tuple[str, int | None]] = [("OPEN", ranks.crl)]
    if student.is_pwd:
        candidates.append(("OPEN-PwD", ranks.crl_pwd))
    category_seat = _CATEGORY_SEAT.get(student.category)
    if category_seat:
        candidates.append((category_seat, ranks.category_rank))
        if student.is_pwd:
            candidates.append((f"{category_seat}-PwD", ranks.category_pwd_rank))
    return [SeatClaim(seat, rank, rank_list_name(exam, seat)) for seat, rank in candidates if rank is not None]


def gender_pools(student: Student) -> list[str]:
    """Female candidates may hold seats from both pools. Others hold gender-neutral seats only."""
    return ["neutral", "female"] if student.gender == "female" else ["neutral"]


def quota_applies(
    quota: str,
    student_state: str | None,
    institute_type: str,
    quota_states: dict[str, set[str]],
) -> tuple[bool, str]:
    """Decide whether a quota is open to the student. Returns (applies, plain-language reason)."""
    if quota == "AI":
        return True, "All India quota is open to every eligible candidate."
    if institute_type in ADVANCED_TYPES:
        return False, "IITs and IISc have All India seats only."
    if student_state is None:
        return False, "State of first Class XII attempt is needed to apply this quota."
    eligible_states = quota_states.get(quota, set())
    if quota == "OS":
        # Other State means outside every state counted as home for this institute (clause 11).
        home = quota_states.get("HS", set()) | quota_states.get("GO", set()) | quota_states.get("JK", set()) | quota_states.get("LA", set())
        if not home:
            return False, "This institute's home states are not recorded, so Other State cannot be decided."
        if student_state in home:
            return False, f"{student_state} counts as a home state for this institute."
        return True, f"Other State quota applies because {student_state} is not a home state here."
    if quota in ("HS", "GO", "JK", "LA"):
        if student_state in eligible_states:
            return True, f"{quota} quota applies to candidates whose Class XII state is {student_state}."
        return False, f"{quota} quota is not open to candidates from {student_state}."
    return False, f"Unknown quota {quota}."


def class12_threshold(student: Student) -> int:
    """Annexure 2(a)/(b): 75% aggregate, or 65% for SC, ST and PwD. Top-20-percentile is the alternative."""
    return 65 if student.category in ("SC", "ST") or student.is_pwd else 75
