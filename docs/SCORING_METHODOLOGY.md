# Scoring methodology

Code: `backend/app/services/scoring.py`. Version `0.3.0`.

There are three separate outputs, and they are never combined: quality, suitability and admission band.

## A. Quality score

| Dimension | Weight | Evidence today |
|---|---:|---|
| Career and placement outcomes | 25 | Institute-wide medians for about 52 institutes, half weight |
| Academic and faculty quality | 18 | None |
| Branch strength and curriculum | 15 | None |
| Alumni and industry network | 12 | None |
| Institutional reputation | 10 | NIRF rank, secondary sources, 49 institutes |
| Financial return | 10 | None |
| Student experience | 5 | None |
| Location and opportunities | 5 | None |

These weights are initial product assumptions, not validated findings.

- Coverage is the share of weight with evidence. **Below 50%, no score is shown.** At most 10% is available today, so no option has a quality score yet. That is the intended behaviour.
- The score is a weighted mean over covered dimensions only.
- Reputation runs from 100 at rank 1 to 50.5 at rank 100. No rank means no evidence and counts as a neutral 50, so being ranked never scores below being absent. NIRF ranks only institutes that take part, so absence doesn't show an institute would rank lower. A programme on a campus abroad gets no rank, because the parent's rank describes its main campus.
- Career uses the self-reported median salary as a percentile among institutes, plus the placement rate among eligible students where that is reported. **The highest package is never used.**
- Salaries are compared only **within one graduating year and one reporting definition**. A NIRF 2025 file covers 2022-24 and a NIRF 2026 file covers 2023-25, so averaging across whole files would be unfair. Years with fewer than 50 institutes aren't used, which today leaves 2023 and 2024.
- Not scored, though figures are still shown: **classes of fewer than 100 graduates**, whose medians are too noisy; **programmes other than 4-year ones**, which that NIRF table doesn't cover; and **Overall submissions**, which aren't comparable with Engineering ones.
- **Branch-level figures are shown first but aren't scored.** Each institute's report defines its base group differently and only 4 institutes publish them, so the score still uses the institute-wide NIRF figure.
- NIRF's "graduating in minimum time" count isn't the eligible group, so no placement rate is calculated from it.
- Institute-wide placement data counts for half coverage and is labelled, because it says nothing specific about a branch.
- Closing rank is not used as quality, because it mostly reflects demand. It would also double-count reputation.

## B. Suitability score
A weighted average from 0 to 100, using the student's priorities.

| Dimension | Rule |
|---|---|
| Branch preference | Preferred 100, acceptable 60, unlisted 25 |
| Career goal | Branch in goal's assumed set 100, otherwise 30. Goals without a branch mapping have no effect |
| Reputation | Same as above |
| Location | Preferred state 100, otherwise 30 |
| Institution type | Preferred 100, otherwise 30 |
| Placements | Career score where evidence exists |
| Affordability | Annual cost compared with budget where tuition, hostel and mess are all published. If the record is partial, it counts only when the recorded charges alone exceed the budget, because a partial sum can't show that a budget is met. Fees aren't applied to students a record doesn't cover, such as SC, ST and PwD students. |
| How contested the seat is | Share of programmes on the same exam that close at a weaker rank, using the mean of the latest three years' OPEN, gender-neutral, All India or Other State closing ranks |

**Unknown dimensions count as a neutral 50**, and the share based on known information is displayed. Otherwise an option with little data could beat one with more evidence just by skipping weak dimensions. This is a scoring convention, not an invented data point.

### Known limits of the placement score
1. **It isn't branch-specific.** Every 4-year branch of an institute gets the same score, which can hide big differences between branches.
2. **Institutes with data differ from those without.** The median of each institute's best closing rank is 22,140 for those with Engineering data, against 59,729 for those without (2026, NIT+ system, OPEN, gender-neutral). Those without data get a neutral 50. So an institute reporting modest results, such as SMVDU Katra at about 5, can rank below one reporting nothing. Filling the gap with a lower value would be inventing a figure, so this limit is disclosed on the Methodology page instead.
3. **Medians cover placed students only.** They say nothing about those who weren't placed. The table shows both counts.
4. **The figures are self-reported** and not audited.
5. **The cohort margin is thin.** At 52 institutes, a few changes could bring a year back under 50.

### Known limit of affordability
With a budget set, an institute that publishes its charges can lose points, while one that publishes nothing stays neutral. The default weight is small, but this can favour institutes with no published fees.

### Why seat contest is in suitability but not quality
Validation in November 2026 showed that the order below about rank 6,000 mostly reflected which institutes publish data, because NIRF ranks cover 26 institutes and scored placements fewer than half. Closing ranks exist for nearly every seat, so they now count for 20 of the default 120 priority points. Students can change that weight, and it is labelled as past candidates' choices.

It stays out of quality, because closing rank mostly reflects demand and would double-count reputation. Main and Advanced programmes are each compared only within their own exam, so a student holding both ranks sees scores on two separate scales. A preferred branch always beats an unlisted one at default weights, but a very contested acceptable branch can beat a barely contested preferred one.

The branch-to-career table (`CAREER_BRANCH_AFFINITY`) is a product assumption and is labelled that way in the interface.

## C. Admission band
See `ADMISSION_ENGINE.md`. Priorities never change bands.

## Ordering
Options with a band come first, followed by those with limited history. Within each group, sort by suitability, then band, institute name, programme name and ID. The same input gives the same output, and each run stores input and result hashes. No LLM is involved, and commercial relationships aren't an input.

## Not yet implemented from the brief
Year adjustment of placement data, like-for-like peer groups beyond scope, correlation checks between indicators, and evidence-confidence scores beyond coverage. All of these need real data to design properly.
