

def test_special_stray_file_is_split_by_course(monkeypatch):
    from ingest import exam_extract
    rows = [
        {"institute": "A", "programme": "MBBS", "group": f"All India · {exam_extract.SPECIAL_STRAY}", "category": "Open", "value": 9, "first_value": 9, "count": 1},
        {"institute": "B", "programme": "BDS", "group": f"All India · {exam_extract.SPECIAL_STRAY}", "category": "Open", "value": 9, "first_value": 9, "count": 1},
    ]
    monkeypatch.setattr(exam_extract, "mcc_records", lambda path, label: (rows, {"source_rows": 2, "sequence_breaks": 0}))
    found, _ = exam_extract.mcc_special_stray_records(None)
    assert [r["group"] for r in found] == ["All India · Special stray round", "All India · Round 5"]
