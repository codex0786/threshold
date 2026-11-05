# Testing strategy

```
cd backend && .venv/bin/python -m pytest
cd frontend && npx tsc --noEmit
```

Backend tests run against the separate `threshold_test` database. All records there are labelled test fixtures with invented institutes, so they can't be mistaken for real data, and they never enter the app database.

## Critical checks from the brief

| Requirement | Test |
|---|---|
| Category rank never confused with CRL | `test_category_rank_is_never_used_for_open_seats_and_crl_never_for_category_seats`, `test_crl_alone_never_unlocks_category_seat` |
| Home-state quota applied correctly | `test_home_state_seat_is_used_for_home_candidate`, `test_goa_special_quota_rules`, `test_srinagar_jk_and_ladakh_quotas` |
| Counselling routes not mixed | `test_counselling_routes_are_not_mixed_between_exams` |
| Institute placements not labelled as branch data | `test_institute_wide_placement_is_labelled_on_branch_view`, `test_schema_blocks_institute_data_stored_as_programme_data` |
| Missing data isn't invented | `test_missing_data_stays_missing`, `test_missing_rank_is_no_evidence_not_a_low_score` |
| History preserved | `test_historical_records_are_kept_per_year` |
| Reproducible | `test_recommendations_are_reproducible_and_logged` |
| Scores respond to preferences | `test_changing_priorities_reorders_results` |
| No probabilities | `test_no_probability_in_any_response_field`, `test_band_has_no_probability_field` |

## Manual browser verification (2026-11-05)
Walked through onboarding, shortlist, explanation panel, priority sliders, compare, college and programme pages, methodology, and phone width. This found and fixed: the menu icon showing on desktop, Continue skipping the last onboarding step, duplicate institute names in trade-offs, sliders pushing results off the first screen on phones, and data pages being frozen at build time.

With the API stopped: the landing page still loads without live figures, Methodology shows an error page, and the shortlist shows an error message. An unknown college returns 404. `npm run build` passes.

A suspected 2026 data fault (identical Round 1 and final values on one seat) was checked and ruled out: 20-26% of seats match this way in every year, and each raw file confirms the requested round.

Importer tests (`tests/test_import.py`) cover dry runs, all-or-nothing behaviour, conflicts, repeat imports, document hashing, and rejection of test fixtures, missing sources and scope errors.

Automated rules for NIRF documents are tested in `tests/test_rules.py` and `tests/test_import.py`: name matching, word cross-checks, single-year comparison, class-size and 5-year exclusions, and keeping Overall apart from Engineering. These rest on the fairness analysis recorded in `SCORING_METHODOLOGY.md`, which was a one-off and isn't automated.

`tests/test_decisions.py` covers cost and EMI arithmetic, preference order never changing, ordering warnings, rank lists in preference analysis, and the parent report's limits. Testing the calculator in the browser found a real bug: it used the 2022 median instead of the newest.

## Gaps
- **Saving as PDF hasn't been tested end to end.** Print styles exist and the button opens the browser's print function, but no PDF output was inspected.
- Drag-and-drop reordering wasn't exercised by hand. The move buttons were, and both use the same function.
- NIRF extraction is tested on sample rows and by the word cross-check, not by an automated test on real PDFs, which stay out of git.
- No automated end-to-end or frontend tests. The flow in section 28 of the brief also needs registration, preference lists and reports, which don't exist yet.
- No load tests and no accessibility audit, although the markup uses labels, roles and contrast tokens.
- Business rules are tested against our reading of the document. No independent reviewer has checked them.
