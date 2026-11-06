# Admission engine

Code: `eligibility.py` and `bands.py`. Authority: JoSAA 2026 Business Rules.

## Eligibility rules

| Rule | Source | Implementation |
|---|---|---|
| IITs and IISc use JEE Advanced. NIT+ uses JEE Main | Clause 2 | `exam_for` |
| B.Arch and B.Plan need Paper 2A or 2B ranks | Clause 2 | Excluded from results, and the student is told |
| Home state is where Class XII was **first** attempted, not residence | Clause 8 | The form asks exactly this |
| Each seat type uses its own rank list | Allotment sequences | `seat_claims`, `rank_list_name` |
| Female candidates can hold both pools. Others hold gender-neutral only | FAQ 11 | `gender_pools` |
| HS, OS and AI seats | Clause 11 | `quota_applies` |
| NIT Goa: GO for Goa, HS for Daman & Diu, Dadra & Nagar Haveli, Lakshadweep | Clause 12 | `QUOTA_OVERRIDES` |
| NIT Srinagar: JK and LA | Clause 12 | `QUOTA_OVERRIDES` |
| Andaman & Nicobar counts as home for NIT Puducherry, Chandigarh for NIT Delhi | Clause 12 | `QUOTA_OVERRIDES` |
| GKCIET Malda: home is the listed north-eastern states | Clause 11 | `QUOTA_OVERRIDES` |
| Class XII: 75%, or 65% for SC, ST, PwD, or top 20 percentile | Annexure 2 | Self-declared. "No" returns no options, with the reason |

**Not checked:** programme-specific medical restrictions, OCI/PIO and foreign candidates, preparatory courses, Class XII year-of-passing limits, supernumerary UT seats. Students are told to check the annexures for special restrictions. OCI/PIO and foreign candidates aren't handled, and the first onboarding step says so.

## Rank safety
A claim holds one rank and the list it belongs to. Before comparing, the list must match the record's `rank_list`. A missing category rank creates no claim, and is never estimated from CRL. `50P`-style preparatory ranks are stored but excluded.

## Bands
Uses final-round closing ranks from the latest three admission years, for the same programme, quota, seat type and pool. At least two years are required.

| Band | Rule (lower rank is better) |
|---|---|
| Safer historical range | rank ≤ 90% of the lowest closing rank |
| Competitive | rank ≤ the highest closing rank |
| Ambitious | rank ≤ 120% of the highest closing rank |
| Beyond | anything further. Hidden from the shortlist, but counted |
| Limited history | under two recent years, and rank within 120% of the one closing rank we have. No band is given, and these are listed after banded options |

With only one recent year, a rank more than 20% past that closing rank counts as Beyond. Programmes with no final-round cutoff in the latest year are hidden and counted, because they may no longer be offered. That can't be confirmed from cutoffs alone. Single seat types can go unfilled, so the check applies to the whole programme.

A student may compete through several routes. The card shows the best one, and the rest are listed.

The 10% and 20% margins are judgement calls, tested below but not optimised.

## Backtest
`python -m ingest.backtest --test-year 2026`

Three earlier years set the band edges. The check is whether a rank exactly at each edge would still have been inside the test year's final closing rank.

| Test year | Seats | Safer edge held | Competitive edge held | Ambitious edge held |
|---|---:|---:|---:|---:|
| 2024 | 8,722 | 94.0% | 39.0% | 9.7% |
| 2025 | 9,522 | 92.8% | 35.9% | 6.4% |
| 2026 | 10,198 | 91.2% | 40.6% | 6.5% |

For OPEN gender-neutral seats alone, the Safer edge held 94.5% to 96.9% of the time.

**How to read this:** it measures whether seats stayed stable, at the worst rank in each band. It is not an individual's chance of admission. It ignores what other applicants choose and the student's own preference order. It doesn't justify showing numerical probabilities, so none are shown. Individual outcomes are not public, so calibration isn't possible.

## Known limitations
- Bands cover JoSAA only. CSAB special round ranks are listed apart, on the common rank list, for 2026 only and with no bands. State routes need separate adapters.
- Only Round 1 and the last round are stored, and only the last round drives bands. Students wanting an early seat may also care about Round 1.
- The 2026 seat matrix decides whether a programme is offered, and removes a route with no seat and no 2026 cutoff. A category with one or two seats gets a warning. Seats don't change a band.
- Renamed programmes share one history, only for pairs reviewed by hand in `data/registry/programme_lineage.yaml`.
- Very small seat pools are noisy, which the "other seats" backtest reflects.
- Programme name changes break history, which shows up as Limited history.
- Rules come from 2026 and are applied to all past years' cutoffs.
