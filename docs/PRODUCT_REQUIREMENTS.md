# Product requirements

Working name: **Threshold**. The name is a placeholder and appears only in the UI, README and docs.

## Promise
Help JEE aspirants and parents decide which college and branch to choose, why, and what outcomes to expect. It is a decision tool, not just a college predictor.

## Non-negotiable principles
1. Never fabricate placements, faculty, alumni, fees, reviews or rankings.
2. Every important data point has a source, a reporting year and a verification status.
3. Keep institute, department and programme data separate. Institute figures are never shown as branch figures.
4. A historical cutoff is never presented as an admission probability.
5. Missing, estimated, outdated and verified data are visibly different.
6. Quality, suitability and admission likelihood stay separate.
7. Recommendations are deterministic and explainable. An LLM may explain results but must not rank them.
8. Paid partnerships never influence organic results.

## Status against the MVP acceptance criteria (brief, section 30)

| # | Criterion | Status |
|---|---|---|
| 1 | Student enters JEE information | **Done** |
| 2 | Options come from stored admission records | **Done**, JoSAA only |
| 3 | Student can filter institutions | **Done** for name, city, type, state and branch. Fee, placement, accreditation and quality filters need data |
| 4 | Institution and programme profiles | **Partial**: cutoffs, NIRF and data completeness work. Curriculum, faculty and facilities show "Data not available" |
| 5 | Source-backed placement and academic data | **Partial**: institute-wide placements for 59 institutes, branch-level for 4, fees for 6, all sourced. No faculty or curriculum |
| 6 | Compare up to four programmes | **Done**, with gaps shown |
| 7 | Transparent quality and suitability scores | **Partial**: suitability works. Quality is correctly withheld because evidence coverage is 10%, below the 50% minimum |
| 8 | Explainable recommendations | **Done** |
| 9 | Preference list | **Done** for JoSAA. Saved in the browser only, as no accounts exist |
| 10 | Financial comparison | **Partial**: calculator for one programme, prefilled from published figures. No side-by-side cost comparison yet |
| 11 | Parent report | **Done**. PDF uses the browser's print function |
| 12 | Admin can update and verify data | **Not built** |

**The MVP is not complete.** The main gaps are admin, accounts, curriculum, department-level faculty, a language model for the assistant, and wider coverage of branch-level data and fees.

## Onboarding fields
Collected now: Class XII state, category, seat pool, PwD status, Class XII criterion, JEE Main and Advanced ranks by list, branch preferences, institution types, states, career goals, annual budget, priorities.

Not collected yet: exam year, preferred cities, total budget, hostel, scholarship and loan preferences. These have no effect until fee and financial features exist, so asking now would mislead students.

Student data stays in the browser. Each shortlist request sends the profile to the API, and the profile is stored with the run for reproducibility. No name or contact details are collected.
