# Data dictionary

Source of truth for built tables: `backend/app/models.py` and `backend/alembic/versions`.

## Built

| Table | Purpose | Key points |
|---|---|---|
| `data_sources` | Source registry | Tier and access status, loaded from `data/registry/sources.yaml` |
| `source_documents` | One retrieved artefact | URL, SHA-256, raw path, reporting year, fetch time |
| `institutions` | Canonical institutes | Slug, type (IIT, IISC, NIT, IIIT, GFTI), location with verification flag, pilot flag |
| `institution_aliases` | Name variants across years | Unique alias. Unknown names stop the load |
| `quota_eligible_states` | Who can hold HS, GO, JK or LA seats | From the states printed in the JoSAA seat matrix |
| `programmes` | Programme per institute | Raw JoSAA name, branch family, degree, duration, required exam paper. `campus_city` and `campus_country` for a campus abroad. `successor_id` for a reviewed rename |
| `cutoff_records` | Published opening and closing ranks | Unique per programme, authority, year, round, quota, seat type and pool. Past years are never overwritten |
| `seat_matrix_records` | Seats published by JoSAA | One row per programme, year, quota, seat type and gender pool. Never used to calculate a chance of admission |
| `csab_cutoffs` | CSAB special round ranks | Kept apart from `cutoff_records` so they can't enter a band. All ranks are on the common rank list |
| `institution_rankings` | NIRF ranks | Verification status required |
| `placement_records` | Placement outcomes | 248 rows: 201 from NIRF plus 1 report row institute-wide, and 46 for individual branches. `base_students` and `base_label` name the group each rate is measured against, and `salary_basis` marks CTC. Keeps total, eligible, graduating, placed, offers and higher studies apart. Has `cohort_label` and `reporting_definition`. A constraint enforces scope consistency |
| `placement_sectors` | Students placed by sector | Per report and cohort |
| `placement_recruiters` | Companies an institute lists | Holds no hiring numbers |
| `alumni_observations` | Aggregate counts from a public sample | No names or person identifiers, by design |
| `fee_records` | Fees by year | 12 rows. Yearly amounts only where the document says they repeat. `payable_at_admission_inr` is the document's own stated total |
| `recommendation_runs` | Reproducibility log | Input snapshot and hashes. No identity fields |
| `audit_logs` | Change log | Written by ingestion and imports, including the file hash |

### `cutoff_records` fields that prevent mistakes
- `rank_list`: the only list this rank may be compared with.
- `is_preparatory`: true for ranks such as `50P`. These are excluded from bands.
- `raw_opening`, `raw_closing`: the exact published text.
- `is_final_round`: the last round offered by the source when fetched.

### Verification status values
`official`, `verified`, `secondary_unverified`, `manual_unverified`, `outdated`, `test_fixture`.

## Planned, not built
From section 23 of the brief: departments, programme_versions, admission_examinations, counselling_authorities, admission_routes, seat_matrices, faculty, faculty_affiliations, research_records, curriculum_records, accreditation_records, scholarships, student_reviews, data_observations, data_verification, data_quality_scores, student_profiles, student_preferences, saved_colleges, comparisons, preference_lists, preference_list_items, counselling_scenarios (preference lists are currently saved in the browser).

Each will be added by migration together with the feature that uses it, so that no empty tables build up without tests. `counselling_authorities` and `admission_examinations` are strings for now and become tables when CSAB is added.

## Branch families
Defined in `app/services/branches.py`. They are a working grouping of JoSAA programme names by keyword, not an official classification. About 40 unusual names fall under `OTHER`.
