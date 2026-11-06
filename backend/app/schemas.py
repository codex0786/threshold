"""Request schemas. The student profile holds no name, contact details or exact address."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.eligibility import Student, StudentRanks
from app.services.scoring import DEFAULT_PRIORITIES

STATES = [
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
    "Dadra and Nagar Haveli", "Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]
Rank = Field(default=None, gt=0, le=2_000_000)


class RankInput(BaseModel):
    crl: int | None = Rank
    category_rank: int | None = Rank
    crl_pwd: int | None = Rank
    category_pwd_rank: int | None = Rank

    def to_domain(self) -> StudentRanks:
        return StudentRanks(self.crl, self.category_rank, self.crl_pwd, self.category_pwd_rank)


class StudentProfile(BaseModel):
    category: Literal["GEN", "GEN-EWS", "OBC-NCL", "SC", "ST"]
    gender: Literal["female", "male", "other"]
    is_pwd: bool = False
    eligibility_state: str = Field(description="State of FIRST Class XII attempt, not residence")
    class12_status: Literal["meets", "does_not_meet", "unknown"] = "unknown"
    main: RankInput = RankInput()
    advanced: RankInput = RankInput()
    advanced_qualified: bool = False

    preferred_branches: list[str] = []
    acceptable_branches: list[str] = []
    avoid_branches: list[str] = []
    preferred_types: list[Literal["IIT", "IISC", "NIT", "IIIT", "GFTI"]] = []
    preferred_states: list[str] = []
    career_goals: list[str] = []
    annual_budget_inr: int | None = Field(default=None, gt=0)
    priorities: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_PRIORITIES))

    @model_validator(mode="after")
    def check_consistency(self) -> "StudentProfile":
        if self.eligibility_state not in STATES:
            raise ValueError("eligibility_state must be a listed state or union territory")
        for name, ranks in (("JEE Main", self.main), ("JEE Advanced", self.advanced)):
            if self.category == "GEN" and (ranks.category_rank or ranks.category_pwd_rank):
                raise ValueError(f"{name}: a category rank was given for the GEN category")
            if not self.is_pwd and (ranks.crl_pwd or ranks.category_pwd_rank):
                raise ValueError(f"{name}: a PwD rank was given without PwD status")
        if self.advanced_qualified and not (self.advanced.crl or self.advanced.category_rank or self.advanced.crl_pwd or self.advanced.category_pwd_rank):
            raise ValueError("JEE Advanced was marked as qualified but no Advanced rank was given")
        if not self.advanced_qualified and any(self.advanced.model_dump().values()):
            raise ValueError("JEE Advanced ranks were given but it is not marked as qualified")
        if not any(self.main.model_dump().values()) and not self.advanced_qualified:
            raise ValueError("Enter at least one JEE rank")
        if set(self.preferred_branches) & set(self.avoid_branches):
            raise ValueError("A branch cannot be both preferred and avoided")
        if any(v < 0 for v in self.priorities.values()):
            raise ValueError("Priorities cannot be negative")
        # Profiles saved in a browser before this factor existed hold every other priority. Partial API requests stay as sent.
        if "demand" not in self.priorities and set(DEFAULT_PRIORITIES) - {"demand", "faculty", "research"} <= set(self.priorities):
            self.priorities["demand"] = DEFAULT_PRIORITIES["demand"]
        return self

    def to_student(self) -> Student:
        return Student(
            category=self.category, gender=self.gender, is_pwd=self.is_pwd, eligibility_state=self.eligibility_state,
            main=self.main.to_domain(), advanced=self.advanced.to_domain(), advanced_qualified=self.advanced_qualified,
        )


class RecommendationRequest(BaseModel):
    profile: StudentProfile
    per_band_limit: int = Field(default=25, ge=1, le=100)


class CounsellingRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    profile: StudentProfile | None = None


class ComparisonRequest(BaseModel):
    programme_ids: list[int] = Field(min_length=2, max_length=4)
    profile: StudentProfile | None = None


class PreferenceListRequest(BaseModel):
    profile: StudentProfile
    programme_ids: list[int] = Field(min_length=1, max_length=200)


class ParentReportRequest(BaseModel):
    profile: StudentProfile
    programme_ids: list[int] = Field(min_length=1, max_length=8)


class RoiRequest(BaseModel):
    annual_tuition_inr: int = Field(default=0, ge=0, le=50_000_000)
    annual_hostel_inr: int = Field(default=0, ge=0, le=50_000_000)
    annual_mess_inr: int = Field(default=0, ge=0, le=50_000_000)
    annual_other_inr: int = Field(default=0, ge=0, le=50_000_000)
    one_time_inr: int = Field(default=0, ge=0, le=50_000_000)
    refundable_deposit_inr: int = Field(default=0, ge=0, le=50_000_000)
    annual_living_inr: int = Field(default=0, ge=0, le=50_000_000)
    annual_scholarship_inr: int = Field(default=0, ge=0, le=50_000_000)
    years: int = Field(default=4, ge=1, le=7)
    family_contribution_inr: int = Field(default=0, ge=0, le=100_000_000)
    loan_amount_inr: int | None = Field(default=None, ge=0, le=100_000_000)
    interest_rate_percent: float = Field(default=9.0, ge=0, le=30)
    repayment_years: int = Field(default=10, ge=1, le=20)
    moratorium_months: int = Field(default=60, ge=0, le=120)
    median_ctc_inr: int | None = Field(default=None, gt=0, le=100_000_000)
    low_ctc_inr: int | None = Field(default=None, gt=0, le=100_000_000)
    high_ctc_inr: int | None = Field(default=None, gt=0, le=100_000_000)
    take_home_share: float = Field(default=0.7, gt=0, le=1)
    repayment_share: float = Field(default=0.4, gt=0, le=1)
