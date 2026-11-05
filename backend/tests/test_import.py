"""Importer tests. All rows are invented fixtures and use the test database."""
import csv
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AuditLog, DataSource, FeeRecord, PlacementRecord
from ingest import import_records
from ingest.import_records import run
from ingest.nirf_pdf import graduation_year, parse_median, rows_from_table, sanity_problems


@pytest.fixture()
def workspace(tmp_path, monkeypatch, seeded):
    monkeypatch.setattr(import_records, "ROOT", tmp_path)
    (tmp_path / "doc.pdf").write_bytes(b"fixture document " + tmp_path.name.encode())
    with SessionLocal() as db:
        if not db.scalar(select(DataSource).where(DataSource.key == "fixture_import")):
            db.add(DataSource(key="fixture_import", name="TEST", publisher="tests", url="n/a", tier="fixture", access_method="n/a", access_status="available"))
            db.commit()
    return tmp_path


def write(path: Path, rows: list[dict]) -> Path:
    file = path / "in.csv"
    with file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({k for r in rows for k in r}))
        writer.writeheader()
        writer.writerows(rows)
    return file


def placement(**kw):
    return {
        "source_key": "fixture_import", "institution_slug": "fixture-nit", "scope": "institution", "cohort_label": "All 4-year UG programmes",
        "reporting_definition": "nirf_graduation_outcomes", "graduation_year": "2025", "graduating_students": "100", "students_placed": "80",
        "median_salary_inr": "1200000", "verification_status": "official", "source_title": "Doc", "source_url": "https://example.org/doc.pdf",
        "source_file": "doc.pdf", "source_page": "1", "reporting_year": "2026", **kw,
    }


def fee(**kw):
    return {
        "source_key": "fixture_import", "institution_slug": "fixture-nit", "academic_year": "2026-27", "seat_type_group": "General, income above 5 lakh",
        "annual_tuition_inr": "125000", "verification_status": "official", "source_title": "Doc", "source_url": "https://example.org/doc.pdf", "source_file": "doc.pdf", **kw,
    }


def do(kind, path, rows, commit=False):
    with SessionLocal() as db:
        return run(db, kind, write(path, rows), commit)


def counts():
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(PlacementRecord)), db.scalar(select(func.count()).select_from(FeeRecord))


def test_dry_run_writes_nothing(workspace):
    before = counts()
    report = do("placements", workspace, [placement()])
    assert report.ok and report.created == 1 and counts() == before


def test_commit_is_recorded_and_rerun_is_idempotent(workspace):
    first = do("placements", workspace, [placement(graduation_year="2024")], commit=True)
    assert first.created == 1
    second = do("placements", workspace, [placement(graduation_year="2024")], commit=True)
    assert second.created == 0 and second.unchanged == 1
    with SessionLocal() as db:
        assert db.scalars(select(AuditLog).where(AuditLog.entity == "placements").order_by(AuditLog.id.desc())).first().detail["file"] == "in.csv"


def test_changed_value_is_a_conflict_not_an_overwrite(workspace):
    do("placements", workspace, [placement(graduation_year="2023")], commit=True)
    report = do("placements", workspace, [placement(graduation_year="2023", median_salary_inr="9999999")], commit=True)
    assert not report.ok and "differs" in report.conflicts[0]
    with SessionLocal() as db:
        assert 9999999 not in db.scalars(select(PlacementRecord.median_salary_inr)).all()


def test_one_bad_row_rejects_the_whole_file(workspace):
    before = counts()
    report = do("placements", workspace, [placement(graduation_year="2022"), placement(graduation_year="2021", students_placed="500")], commit=True)
    assert not report.ok and "exceeds" in report.errors[0] and counts() == before


@pytest.mark.parametrize("change,message", [
    ({"verification_status": "test_fixture"}, "test fixtures"),
    ({"verification_status": "looks fine"}, "unknown verification_status"),
    ({"source_url": ""}, "source_url is required"),
    ({"source_title": ""}, "source_title is required"),
    ({"source_file": ""}, "source_file is required"),
    ({"source_file": "missing.pdf"}, "not found"),
    ({"institution_slug": "nope"}, "unknown institution_slug"),
    ({"scope": "programme"}, "needs a programme_id"),
    ({"programme_id": "1"}, "cannot name a programme"),
    ({"reporting_definition": ""}, "reporting_definition"),
    ({"cohort_label": ""}, "cohort_label"),
    ({"median_salary_inr": "12"}, "plausible"),
    ({"median_salary_inr": "12 lakh"}, "whole number"),
    ({"median_salary_inr": "", "students_placed": ""}, "at least a median"),
    ({"source_key": "unknown"}, "unknown source_key"),
])
def test_invalid_placement_rows_are_rejected(workspace, change, message):
    report = do("placements", workspace, [placement(**change)])
    assert not report.ok and any(message in e for e in report.errors), report.errors


def test_programme_must_belong_to_the_institute(workspace, seeded):
    report = do("placements", workspace, [placement(scope="programme", programme_id=str(seeded["cse_two"]))])
    assert any("does not belong" in e for e in report.errors)


def test_duplicate_rows_are_rejected(workspace):
    report = do("placements", workspace, [placement(graduation_year="2020"), placement(graduation_year="2020")])
    assert any("duplicate" in e for e in report.errors)


def test_exact_document_is_hashed(workspace):
    do("placements", workspace, [placement(graduation_year="2019")], commit=True)
    with SessionLocal() as db:
        record = db.scalars(select(PlacementRecord).where(PlacementRecord.graduation_year == 2019)).first()
        assert record.source_document.sha256 == hashlib.sha256((workspace / "doc.pdf").read_bytes()).hexdigest()


def test_fee_import_and_rules(workspace):
    assert do("fees", workspace, [fee()], commit=True).created == 1
    assert any("seat_type_group" in e for e in do("fees", workspace, [fee(seat_type_group="", academic_year="2025-26")]).errors)
    assert any("academic_year" in e for e in do("fees", workspace, [fee(academic_year="2026")]).errors)
    assert any("at least one amount" in e for e in do("fees", workspace, [fee(annual_tuition_inr="", academic_year="2024-25")]).errors)


def test_partial_fee_gives_no_annual_cost_and_a_gap(client, seeded, workspace):
    do("fees", workspace, [fee(institution_slug="fixture-goa")], commit=True)
    body = client.post("/api/v1/comparisons", json={"programme_ids": [seeded["goa_cse"], seeded["cse"]]}).json()
    goa = body["items"][0]
    assert goa["fee"]["annual_complete_inr"] is None and any("partial" in g for g in goa["data_gaps"])


def test_median_digits_only_come_from_the_leading_number():
    assert parse_median("1700000(Seventeen Lakh)") == 1700000
    assert parse_median("<N/A>") is None
    assert parse_median("Seventeen lakh") is None


def test_nirf_academic_year_maps_to_graduation_year():
    assert graduation_year("2024-25") == 2025
    assert graduation_year("garbled") is None


def test_nirf_row_sanity_checks():
    rows = [["h"] * 10, ["2021-22", "100", "100", "2022-23", "0", "2024-25", "90", "95", "1200000(Twelve)", "5"]]
    parsed, problems = rows_from_table(rows, 1)
    assert parsed[0].graduation_year == 2025 and parsed[0].median_salary_inr == 1200000
    assert any("exceeds" in p for p in problems)
    assert sanity_problems(parsed[0])


def test_dry_run_reports_what_the_database_would_reject(workspace):
    report = do("fees", workspace, [fee(seat_type_group="x" * 200, academic_year="2023-24")])
    assert not report.ok and "database rejected" in report.errors[0]


def test_cohorts_keep_engineering_and_overall_submissions_apart(client, seeded):
    from app.db import SessionLocal
    from app.services.recommend import institution_evidence
    with SessionLocal() as db:
        document_id = db.scalar(select(PlacementRecord.source_document_id).limit(1))
        inst_id = db.scalar(select(PlacementRecord.institution_id).limit(1))
        db.add(PlacementRecord(
            institution_id=inst_id, scope="institution", cohort_label="TEST overall", reporting_definition="nirf_graduation_outcomes_overall",
            graduation_year=2018, median_salary_inr=1500000, verification_status="test_fixture", source_document_id=document_id,
        ))
        db.commit()
        cohorts = institution_evidence(db)["cohorts"]
    assert ("institution", "nirf_graduation_outcomes_overall") in cohorts
    assert cohorts[("institution", "nirf_graduation_outcomes_overall")][2018] == [1500000.0]


def test_four_year_figures_are_not_scored_for_a_five_year_programme(seeded):
    from types import SimpleNamespace
    from app.services import recommend
    record = SimpleNamespace(
        scope="institution", cohort_label="All 4-year UG programmes", programme_id=None, graduation_year=2024, median_salary_inr=2000000,
        eligible_students=None, students_placed=300, reporting_definition="nirf_graduation_outcomes", graduating_students=400,
        source_document=SimpleNamespace(reporting_year=2026),
    )
    evidence = {"placements": {7: [record]}, "cohorts": {("institution", "nirf_graduation_outcomes"): {2024: [2000000.0] * 60}}}
    five = SimpleNamespace(id=1, institution_id=7, duration_years=5)
    four = SimpleNamespace(id=2, institution_id=7, duration_years=4)
    assert recommend.career_for(five, evidence)[1][0] is None and "5 years" in recommend.career_for(five, evidence)[1][1]
    assert recommend.career_for(four, evidence)[1][0] is not None


def test_sector_and_recruiter_imports_need_sources(workspace):
    base = {"source_key": "fixture_import", "institution_slug": "fixture-nit", "academic_year": "2024-25", "verification_status": "official", "source_title": "Doc", "source_url": "https://example.org/doc.pdf", "source_file": "doc.pdf"}
    assert do("sectors", workspace, [{**base, "cohort_label": "All B.Tech", "sector": "IT", "students": "10"}], commit=True).created == 1
    assert do("recruiters", workspace, [{**base, "company_name": "Fixture Co"}], commit=True).created == 1
    assert any("students is required" in e for e in do("sectors", workspace, [{**base, "cohort_label": "x", "sector": "y", "students": ""}]).errors)
    assert any("source_url" in e for e in do("recruiters", workspace, [{**base, "company_name": "Other", "source_url": ""}]).errors)


def test_branch_rows_resolve_by_programme_name_and_need_a_named_base(workspace):
    row = placement(scope="programme", programme_name="Civil Engineering", graduation_year="2017", base_students="100", base_label="registered students")
    assert do("placements", workspace, [row]).ok
    assert any("base_label" in e for e in do("placements", workspace, [{**row, "base_label": ""}]).errors)
    assert any("found 0 programmes" in e for e in do("placements", workspace, [{**row, "programme_name": "Astrology"}]).errors)
    assert any("exceeds" in e for e in do("placements", workspace, [{**row, "students_placed": "101"}]).errors)


def test_branch_and_institute_figures_stay_separate_in_a_comparison(client, seeded, workspace):
    row = placement(scope="programme", programme_name="Computer Science and Engineering", institution_slug="fixture-nit-two", graduation_year="2016", base_students="100", base_label="eligible students", reporting_definition="institute_placement_report", salary_basis="CTC", median_salary_inr="2000000")
    do("placements", workspace, [row], commit=True)
    body = client.post("/api/v1/comparisons", json={"programme_ids": [seeded["cse_two"], seeded["ece_two"]]}).json()
    cse, ece = body["items"]
    assert cse["placements"][0]["scope"] == "programme" and cse["placements"][0]["base_label"] == "eligible students"
    assert all(p["scope"] != "programme" for p in ece["placements"])
    assert any("Branch-level median" in t for t in body["trade_offs"])
    assert not any("Placement data is institute-wide only" in g for g in cse["data_gaps"])


def test_career_profile_withholds_small_alumni_samples_and_holds_no_names(seeded):
    from app.models import AlumniObservation, Institution, SourceDocument
    from app.services import careers
    with SessionLocal() as db:
        inst = db.scalar(select(Institution).where(Institution.slug == "fixture-goa"))
        source_id = db.scalar(select(DataSource.id).limit(1))
        doc_id = db.scalar(select(SourceDocument.id).limit(1))
        db.add(AlumniObservation(institution_id=inst.id, dimension="sample", category="All documented people", people=5, sample_size=5, source_id=source_id, source_document_id=doc_id))
        db.commit()
        result = careers.alumni_sample(db, inst.id)
    assert result["status"] == "too_small" and "occupations" not in result and "not the alumni network" in result["caveat"]
    assert not any(hasattr(AlumniObservation, field) for field in ("person_name", "person_id", "name"))
