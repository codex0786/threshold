"""Tests run on a separate database. Every record here is a clearly labelled test fixture."""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://localhost/threshold_test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db import SessionLocal, engine, get_db
from app.main import app
from app.models import (
    AcademicSnapshot, AcademicYearRecord, Base, CsabCutoff, CutoffRecord, DataSource, FeeRecord, Institution, InstitutionRanking, PlacementRecord, Programme, QuotaEligibleState, SeatMatrixRecord, SourceDocument,
)
from app.services.eligibility import exam_for, rank_list_name


@pytest.fixture(scope="session", autouse=True)
def schema():
    assert "threshold_test" in str(engine.url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def _programme(db, inst, name, family="CS", paper=None):
    programme = Programme(
        institution_id=inst.id, raw_name=f"{name} (4 Years, Bachelor of Technology)", name=name, branch_family=family,
        degree="Bachelor of Technology", duration_years=4, required_paper=paper or ("advanced" if inst.institute_type == "IIT" else "main_paper1"),
    )
    db.add(programme)
    db.flush()
    return programme


def _cutoffs(db, programme, inst, doc, quota, seat, pool, closings):
    for year, closing in closings.items():
        db.add(CutoffRecord(
            programme_id=programme.id, authority="JOSAA", year=year, round=6, is_final_round=True, quota=quota, seat_type=seat,
            gender_pool=pool, rank_list=rank_list_name(exam_for(inst.institute_type), seat), opening_rank=max(1, closing // 2),
            closing_rank=closing, is_preparatory=False, raw_opening=str(max(1, closing // 2)), raw_closing=str(closing), source_document_id=doc.id,
        ))


@pytest.fixture(scope="session")
def seeded(schema):
    with SessionLocal() as db:
        source = DataSource(key="fixture", name="TEST FIXTURE", publisher="tests", url="n/a", tier="fixture", access_method="n/a", access_status="available")
        db.add(source)
        db.flush()
        doc = SourceDocument(source_id=source.id, title="TEST FIXTURE document", url="n/a", sha256="f" * 64, reporting_year=2026)
        db.add(doc)
        db.flush()
        nit = Institution(slug="fixture-nit", official_name="Fixture NIT", short_name="Fixture NIT", institute_type="NIT", city="X", state="Karnataka")
        other_nit = Institution(slug="fixture-nit-two", official_name="Fixture NIT Two", short_name="Fixture NIT Two", institute_type="NIT", city="Y", state="Kerala")
        iit = Institution(slug="fixture-iit", official_name="Fixture IIT", short_name="Fixture IIT", institute_type="IIT", city="Z", state="Karnataka")
        goa = Institution(slug="fixture-goa", official_name="Fixture NIT Goa", short_name="Fixture NIT Goa", institute_type="NIT", city="G", state="Goa")
        db.add_all([nit, other_nit, iit, goa])
        db.flush()
        db.add_all([
            QuotaEligibleState(institution_id=nit.id, quota="HS", state="Karnataka"),
            QuotaEligibleState(institution_id=other_nit.id, quota="HS", state="Kerala"),
            QuotaEligibleState(institution_id=goa.id, quota="GO", state="Goa"),
            QuotaEligibleState(institution_id=goa.id, quota="HS", state="Daman and Diu"),
        ])
        cse = _programme(db, nit, "Computer Science and Engineering")
        civil = _programme(db, nit, "Civil Engineering", "CIVIL")
        cse_two = _programme(db, other_nit, "Computer Science and Engineering")
        ece_two = _programme(db, other_nit, "Electronics and Communication Engineering", "ECE")
        iit_cse = _programme(db, iit, "Computer Science and Engineering")
        arch = _programme(db, nit, "Architecture", "ARCH", paper="main_paper2a")
        goa_cse = _programme(db, goa, "Computer Science and Engineering")
        new_seat = _programme(db, other_nit, "Mechatronics Engineering", "ROBOTICS")
        old_seat = _programme(db, other_nit, "Production Engineering", "ME")
        years = (2024, 2025, 2026)
        for programme, inst, quota, seat, pool, value in [
            (cse, nit, "HS", "OPEN", "neutral", 20000), (cse, nit, "OS", "OPEN", "neutral", 5000),
            (cse, nit, "HS", "OBC-NCL", "neutral", 2000), (cse, nit, "OS", "OPEN", "female", 9000),
            (civil, nit, "OS", "OPEN", "neutral", 40000), (civil, nit, "HS", "OPEN", "neutral", 60000),
            (cse_two, other_nit, "OS", "OPEN", "neutral", 11000), (cse_two, other_nit, "HS", "OPEN", "neutral", 30000),
            (ece_two, other_nit, "OS", "OPEN", "neutral", 13000),
            (iit_cse, iit, "AI", "OPEN", "neutral", 500), (arch, nit, "OS", "OPEN", "neutral", 999999),
            (goa_cse, goa, "GO", "OPEN", "neutral", 50000), (goa_cse, goa, "HS", "OPEN", "neutral", 70000), (goa_cse, goa, "OS", "OPEN", "neutral", 15000),
        ]:
            _cutoffs(db, programme, inst, doc, quota, seat, pool, {y: value for y in years})
        _cutoffs(db, new_seat, other_nit, doc, "OS", "OPEN", "neutral", {2026: 20000})
        _cutoffs(db, old_seat, other_nit, doc, "OS", "OPEN", "neutral", {2024: 90000, 2025: 90000})
        # A programme JoSAA renamed: the earlier name's history belongs to the later one.
        renamed_old = _programme(db, other_nit, "Computer Engineering")
        renamed_new = _programme(db, other_nit, "Computer Engineering and Systems")
        renamed_old.successor_id = renamed_new.id
        _cutoffs(db, renamed_old, other_nit, doc, "OS", "OPEN", "neutral", {2024: 16000, 2025: 16000})
        _cutoffs(db, renamed_new, other_nit, doc, "OS", "OPEN", "neutral", {2026: 16000})
        # A campus abroad doesn't inherit the parent institute's rank.
        abroad = _programme(db, iit, "Abu Dhabi Campus - Computer Science and Engineering")
        abroad.campus_city, abroad.campus_country = "Abu Dhabi", "United Arab Emirates"
        _cutoffs(db, abroad, iit, doc, "AI", "OPEN", "neutral", {y: 9000 for y in years})
        # Seats: a thin category, and one with cutoffs in the past but no seat this year.
        thin = _programme(db, goa, "Ceramic Engineering", "CHEM_E")
        gone = _programme(db, goa, "Textile Technology", "OTHER")
        _cutoffs(db, thin, goa, doc, "OS", "OPEN", "neutral", {y: 80000 for y in years})
        _cutoffs(db, gone, goa, doc, "OS", "OPEN", "neutral", {2024: 80000, 2025: 80000})
        _cutoffs(db, gone, goa, doc, "OS", "SC", "neutral", {y: 80000 for y in years})
        for programme, seat, count in [(thin, "OPEN", 2), (gone, "OPEN", 0), (gone, "SC", 3)]:
            db.add(SeatMatrixRecord(programme_id=programme.id, year=2026, quota="OS", seat_type=seat, gender_pool="neutral", seats=count, source_document_id=doc.id))
        # The matrix lists every programme with a 2026 cutoff, as the real one does, so old_seat alone is missing.
        db.flush()
        current = db.scalars(select(CutoffRecord.programme_id).where(CutoffRecord.year == 2026).distinct()).all()
        for programme_id in current:
            db.add(SeatMatrixRecord(programme_id=programme_id, year=2026, quota="OS", seat_type="ST-PwD", gender_pool="neutral", seats=1, source_document_id=doc.id))
        # CSAB rows sit apart, including a rank far beyond anything JoSAA closed at.
        db.flush()
        for programme, quota, seat, closing in [(civil, "OS", "OPEN", 400000), (cse_two, "HS", "OPEN", 500000), (civil, "OS", "SC", 600000)]:
            db.add(CsabCutoff(programme_id=programme.id, year=2026, round=2, quota=quota, seat_type=seat, gender_pool="neutral", opening_rank=closing - 10, closing_rank=closing, source_document_id=doc.id))
        # Faculty totals exist for one institute only, so others must show nothing.
        db.add(AcademicSnapshot(institution_id=nit.id, submission_year=2026, category="Engineering", faculty_listed=120, faculty_current=110, faculty_regular=100, faculty_with_phd=90, professors=20, associate_professors=30, assistant_professors=50, median_experience_months=120, students_total=1500, phd_students=200, verification_status="test_fixture", source_document_id=doc.id))
        db.add(AcademicYearRecord(institution_id=nit.id, submission_year=2026, category="Engineering", academic_year="2024-25", phd_graduated=30, sponsored_projects=40, sponsored_amount_inr=50_000_000, patents_granted=3, library_spend_inr=1_000_000, equipment_spend_inr=9_000_000, verification_status="test_fixture", source_document_id=doc.id))
        # One branch's median and a partial fee, so an institute-level answer can't borrow the branch figure.
        db.add(PlacementRecord(institution_id=goa.id, programme_id=goa_cse.id, scope="programme", cohort_label="TEST branch cohort", reporting_definition="institute_placement_report", graduation_year=2025, students_placed=50, median_salary_inr=1_234_000, verification_status="test_fixture", source_document_id=doc.id))
        db.add(FeeRecord(institution_id=goa.id, academic_year="2026-27", seat_type_group="General/OBC-NCL/EWS, TEST", annual_tuition_inr=100_000, verification_status="test_fixture", source_document_id=doc.id))
        # A preparatory rank must never be treated as a normal numeric cutoff.
        db.add(CutoffRecord(
            programme_id=iit_cse.id, authority="JOSAA", year=2026, round=6, is_final_round=True, quota="AI", seat_type="SC-PwD", gender_pool="neutral",
            rank_list="JEE_ADVANCED:SC-PwD", opening_rank=50, closing_rank=50, is_preparatory=True, raw_opening="50P", raw_closing="50P", source_document_id=doc.id,
        ))
        db.add(InstitutionRanking(institution_id=nit.id, framework="NIRF", category="Engineering", year=2025, rank=10, score=70, verification_status="test_fixture", source_id=source.id))
        db.add(PlacementRecord(
            institution_id=other_nit.id, scope="institution", cohort_label="TEST cohort", reporting_definition="institute_placement_report", graduation_year=2025, eligible_students=100, students_placed=80,
            median_salary_inr=1_000_000, verification_status="test_fixture", source_document_id=doc.id,
        ))
        db.commit()
        ids = {"renamed_old": renamed_old.id, "renamed_new": renamed_new.id, "abroad": abroad.id, "thin": thin.id, "gone": gone.id, "cse": cse.id, "civil": civil.id, "cse_two": cse_two.id, "ece_two": ece_two.id, "iit_cse": iit_cse.id, "arch": arch.id, "goa_cse": goa_cse.id, "new_seat": new_seat.id, "old_seat": old_seat.id}
    yield ids
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE recommendation_runs"))


@pytest.fixture()
def client(seeded):
    def override():
        with SessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
