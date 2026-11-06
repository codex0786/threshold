"""Database schema for the vertical slice. See docs/DATA_DICTIONARY.md for the full plan."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


VERIFICATION_CHECK = "verification_status IN ('official', 'secondary_unverified', 'manual_unverified', 'verified', 'outdated', 'test_fixture')"


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    publisher: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(32))  # official | secondary | manual | fixture
    access_method: Mapped[str] = mapped_column(Text)
    access_status: Mapped[str] = mapped_column(String(32))  # available | blocked | manual_only | planned
    terms_note: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceDocument(Base):
    """One retrieved artefact. Raw files stay on disk, separate from validated records."""

    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("source_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    raw_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    reporting_year: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    row_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[DataSource] = relationship()


class Institution(Base):
    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint("institute_type IN ('IIT','IISC','NIT','IIIT','GFTI')", name="institute_type_valid"),
        Index("ix_institutions_state", "state"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    official_name: Mapped[str] = mapped_column(Text)
    short_name: Mapped[str] = mapped_column(String(80))
    institute_type: Mapped[str] = mapped_column(String(8))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(Text)
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    # Location comes from the name or general reference until reviewed against official pages.
    location_verification: Mapped[str] = mapped_column(String(32), default="manual_unverified")
    aliases: Mapped[list["InstitutionAlias"]] = relationship(back_populates="institution", cascade="all, delete-orphan")
    programmes: Mapped[list["Programme"]] = relationship(back_populates="institution")
    rankings: Mapped[list["InstitutionRanking"]] = relationship(back_populates="institution")
    quota_states: Mapped[list["QuotaEligibleState"]] = relationship(back_populates="institution", cascade="all, delete-orphan")


class InstitutionAlias(Base):
    __tablename__ = "institution_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(Text, unique=True)
    institution: Mapped[Institution] = relationship(back_populates="aliases")


class QuotaEligibleState(Base):
    """Which states' candidates may hold a quota at an institute. Authority: Business Rules 11-12."""

    __tablename__ = "quota_eligible_states"
    __table_args__ = (UniqueConstraint("institution_id", "quota", "state"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))
    quota: Mapped[str] = mapped_column(String(4))  # HS | GO | JK | LA
    state: Mapped[str] = mapped_column(String(80))
    institution: Mapped[Institution] = relationship(back_populates="quota_states")


class Programme(Base):
    __tablename__ = "programmes"
    __table_args__ = (UniqueConstraint("institution_id", "raw_name"), Index("ix_programmes_family", "branch_family"))
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    raw_name: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    branch_family: Mapped[str] = mapped_column(String(32))
    degree: Mapped[str | None] = mapped_column(Text)
    duration_years: Mapped[int | None] = mapped_column(Integer)
    # Rank list paper needed: main_paper1 | main_paper2a | main_paper2b | advanced
    required_paper: Mapped[str] = mapped_column(String(16))
    # Set only when the programme runs away from the institute's main campus, e.g. IIT Delhi in Abu Dhabi.
    campus_city: Mapped[str | None] = mapped_column(String(80))
    campus_country: Mapped[str | None] = mapped_column(String(80))
    # The later name of this programme, from the reviewed list in programme_lineage.yaml.
    successor_id: Mapped[int | None] = mapped_column(ForeignKey("programmes.id"))
    institution: Mapped[Institution] = relationship(back_populates="programmes")


class CutoffRecord(Base):
    """A published opening/closing rank. A historical fact, never an admission probability."""

    __tablename__ = "cutoff_records"
    __table_args__ = (
        UniqueConstraint("programme_id", "authority", "year", "round", "quota", "seat_type", "gender_pool", name="uq_cutoff_identity"),
        CheckConstraint("gender_pool IN ('neutral','female')", name="gender_pool_valid"),
        CheckConstraint("seat_type IN ('OPEN','EWS','OBC-NCL','SC','ST','OPEN-PwD','EWS-PwD','OBC-NCL-PwD','SC-PwD','ST-PwD')", name="seat_type_valid"),
        CheckConstraint("quota IN ('AI','HS','OS','GO','JK','LA')", name="quota_valid"),
        Index("ix_cutoff_lookup", "year", "round", "seat_type", "quota", "gender_pool"),
        Index("ix_cutoff_programme", "programme_id", "year"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"))
    authority: Mapped[str] = mapped_column(String(16))  # JOSAA now. CSAB and state adapters later.
    year: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer)
    is_final_round: Mapped[bool] = mapped_column(Boolean)
    quota: Mapped[str] = mapped_column(String(4))
    seat_type: Mapped[str] = mapped_column(String(16))
    gender_pool: Mapped[str] = mapped_column(String(8))
    # A rank is only comparable with ranks on the same list, e.g. JEE_MAIN:OBC-NCL.
    rank_list: Mapped[str] = mapped_column(String(40))
    opening_rank: Mapped[int | None] = mapped_column(Integer)
    closing_rank: Mapped[int | None] = mapped_column(Integer)
    is_preparatory: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_opening: Mapped[str] = mapped_column(String(16))
    raw_closing: Mapped[str] = mapped_column(String(16))
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    programme: Mapped[Programme] = relationship()
    source_document: Mapped[SourceDocument] = relationship()


class SeatMatrixRecord(Base):
    """Seats a programme offers in one quota, category and gender pool, as JoSAA publishes them."""

    __tablename__ = "seat_matrix_records"
    __table_args__ = (
        UniqueConstraint("programme_id", "year", "quota", "seat_type", "gender_pool", name="uq_seat_identity"),
        CheckConstraint("seats >= 0", name="seats_not_negative"),
        Index("ix_seats_programme", "programme_id", "year"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"))
    year: Mapped[int] = mapped_column(Integer)
    quota: Mapped[str] = mapped_column(String(4))
    seat_type: Mapped[str] = mapped_column(String(16))
    gender_pool: Mapped[str] = mapped_column(String(8))
    seats: Mapped[int] = mapped_column(Integer)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    programme: Mapped[Programme] = relationship()
    source_document: Mapped[SourceDocument] = relationship()


class CsabCutoff(Base):
    """A CSAB special round rank. Kept apart from JoSAA because every rank here is on the common list and only vacant seats are offered."""

    __tablename__ = "csab_cutoffs"
    __table_args__ = (
        UniqueConstraint("programme_id", "year", "round", "quota", "seat_type", "gender_pool", name="uq_csab_identity"),
        Index("ix_csab_lookup", "year", "quota", "seat_type", "gender_pool"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"))
    year: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer)
    quota: Mapped[str] = mapped_column(String(4))
    seat_type: Mapped[str] = mapped_column(String(16))
    gender_pool: Mapped[str] = mapped_column(String(8))
    opening_rank: Mapped[int | None] = mapped_column(Integer)
    closing_rank: Mapped[int | None] = mapped_column(Integer)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    programme: Mapped[Programme] = relationship()
    source_document: Mapped[SourceDocument] = relationship()


class InstitutionRanking(Base):
    __tablename__ = "institution_rankings"
    __table_args__ = (
        UniqueConstraint("institution_id", "framework", "category", "year"),
        CheckConstraint(VERIFICATION_CHECK, name="ranking_verification_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    framework: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32))
    year: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    verification_status: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    institution: Mapped[Institution] = relationship(back_populates="rankings")
    source: Mapped[DataSource] = relationship()


class PlacementRecord(Base):
    """Scope is explicit, and the constraint stops institute data being stored as branch data."""

    __tablename__ = "placement_records"
    __table_args__ = (
        UniqueConstraint("institution_id", "programme_id", "cohort_label", "graduation_year", "source_document_id", name="uq_placement", postgresql_nulls_not_distinct=True),
        CheckConstraint(
            "(scope = 'programme' AND programme_id IS NOT NULL) OR (scope = 'institution' AND programme_id IS NULL)",
            name="placement_scope_consistent",
        ),
        CheckConstraint(VERIFICATION_CHECK, name="placement_verification_valid"),
        CheckConstraint("students_placed IS NULL OR eligible_students IS NULL OR students_placed <= eligible_students", name="placed_le_eligible"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    programme_id: Mapped[int | None] = mapped_column(ForeignKey("programmes.id"))
    scope: Mapped[str] = mapped_column(String(16))
    # Who the row covers, e.g. "All 4-year UG programmes". Rows are compared only within one definition.
    cohort_label: Mapped[str] = mapped_column(Text)
    reporting_definition: Mapped[str] = mapped_column(String(40))
    graduation_year: Mapped[int] = mapped_column(Integer)
    total_students: Mapped[int | None] = mapped_column(Integer)
    eligible_students: Mapped[int | None] = mapped_column(Integer)
    # NIRF counts students graduating in minimum time. That is not the same as eligible for placement.
    graduating_students: Mapped[int | None] = mapped_column(Integer)
    students_placed: Mapped[int | None] = mapped_column(Integer)
    higher_studies_students: Mapped[int | None] = mapped_column(Integer)
    # The group a report measures placement against. Registered and eligible are different groups.
    base_students: Mapped[int | None] = mapped_column(Integer)
    base_label: Mapped[str | None] = mapped_column(Text)
    salary_basis: Mapped[str | None] = mapped_column(String(32))
    total_offers: Mapped[int | None] = mapped_column(Integer)
    median_salary_inr: Mapped[int | None] = mapped_column(BigInteger)
    average_salary_inr: Mapped[int | None] = mapped_column(BigInteger)
    highest_domestic_salary_inr: Mapped[int | None] = mapped_column(BigInteger)
    verification_status: Mapped[str] = mapped_column(String(32))
    source_page: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    source_document: Mapped[SourceDocument] = relationship()


class PlacementSector(Base):
    __tablename__ = "placement_sectors"
    __table_args__ = (
        UniqueConstraint("institution_id", "academic_year", "cohort_label", "sector", "source_document_id", name="uq_placement_sector"),
        CheckConstraint(VERIFICATION_CHECK, name="sector_verification_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    academic_year: Mapped[str] = mapped_column(String(9))
    cohort_label: Mapped[str] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(String(80))
    students: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(32))
    source_page: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    source_document: Mapped[SourceDocument] = relationship()


class PlacementRecruiter(Base):
    """A company an institute lists as a recruiter. It says nothing about how many it hired or from which branch."""

    __tablename__ = "placement_recruiters"
    __table_args__ = (
        UniqueConstraint("institution_id", "academic_year", "company_name", "source_document_id", name="uq_placement_recruiter"),
        CheckConstraint(VERIFICATION_CHECK, name="recruiter_verification_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    academic_year: Mapped[str] = mapped_column(String(9))
    company_name: Mapped[str] = mapped_column(String(120))
    verification_status: Mapped[str] = mapped_column(String(32))
    source_page: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    source_document: Mapped[SourceDocument] = relationship()


class AlumniObservation(Base):
    """Aggregate counts from a public sample. Holds no names or person identifiers, by design."""

    __tablename__ = "alumni_observations"
    __table_args__ = (Index("ix_alumni_institution", "institution_id", "dimension"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    dimension: Mapped[str] = mapped_column(String(24))  # sample | founder | occupation | employer
    category: Mapped[str] = mapped_column(Text)
    people: Mapped[int] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    source_document: Mapped[SourceDocument] = relationship()


class FeeRecord(Base):
    __tablename__ = "fee_records"
    __table_args__ = (
        UniqueConstraint("institution_id", "academic_year", "seat_type_group", "source_document_id", name="uq_fee"),
        CheckConstraint(VERIFICATION_CHECK, name="fee_verification_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    programme_id: Mapped[int | None] = mapped_column(ForeignKey("programmes.id"))
    academic_year: Mapped[str] = mapped_column(String(9))
    seat_type_group: Mapped[str] = mapped_column(String(120), default="general")
    annual_tuition_inr: Mapped[int | None] = mapped_column(BigInteger)
    annual_hostel_inr: Mapped[int | None] = mapped_column(BigInteger)
    annual_mess_inr: Mapped[int | None] = mapped_column(BigInteger)
    annual_other_inr: Mapped[int | None] = mapped_column(BigInteger)
    one_time_inr: Mapped[int | None] = mapped_column(BigInteger)
    refundable_deposit_inr: Mapped[int | None] = mapped_column(BigInteger)
    # The total the document itself states for the first payment, so nothing is assumed to repeat.
    payable_at_admission_inr: Mapped[int | None] = mapped_column(BigInteger)
    verification_status: Mapped[str] = mapped_column(String(32))
    source_page: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    source_document: Mapped[SourceDocument] = relationship()


class RecommendationRun(Base):
    """Stores inputs and outputs so a run can be reproduced and audited. No names or contact details."""

    __tablename__ = "recommendation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    engine_version: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    result_count: Mapped[int] = mapped_column(Integer)
    result_hash: Mapped[str] = mapped_column(String(64))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
