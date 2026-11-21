# Development roadmap

The brief's phases were reordered slightly. Its first vertical slice crosses Phases 1, 3, 5 and 6, so parts of each are done.

| Phase | Scope | Status |
|---|---|---|
| 0 | Inspection, architecture, docs | **Done** |
| 1 | Database, auth, master data, admin foundation | **Partial**: database and master data done. Auth and admin not built |
| 2 | Source registry, imports, verification | **Partial**: registry, JoSAA ingestion, NIRF PDF extraction and validated CSV import done. Excel, review queue not built |
| 3 | Admission intelligence | **Mostly done** for JoSAA, with the seat matrix and one year of CSAB ranks |
| 4 | Placements, faculty, fees, finance | **Partial**: placements, recruiters, sectors, an alumni sample, fees, institute-wide faculty and research figures, and the calculator are in. Curriculum and department-level faculty aren't |
| 5 | Decision engine | **Partial**: suitability, bands, comparison done. Quality awaits data |
| 6 | User experience | **Partial**: 11 of the 15 sections built |
| 7 | AI counselling | **Partial**: a rule-based assistant answers from stored records through fixed tools. There is no language model or RAG yet, because that needs an API key and approval for a paid service |
| 8 | Reports, PDF export | **Partial**: parent report and preference list save through browser printing. Feature access controls not started |
| 9 | Hardening and deployment | Not started |

## Sections from the brief (section 6)
Built: landing, onboarding, discovery, college profile, programme profile, comparison, recommendations, methodology, preference list, financial calculator, parent report. Admission prediction is part of recommendations.

Rule-based assistant built at `/assistant`.

Not built: student dashboard, admin dashboard.

## Done in the first prioritised slice (November 2026)
- Anonymous usage counts (Vercel Web Analytics) with key events.
- "What the bands mean" card on the shortlist and preference list, with the backtest figures in plain words.
- Share links for the profile and a preference list, with no account.

## Done in the second slice (November 2026)
- Percentile-to-rank estimator (`/rank-estimator`, `POST /estimates/rank`), checked against NTA's published JEE Advanced qualifier counts for 2024–2026.
- Choice-list builder (`POST /preference-lists/build`) with a safety net of Safer choices, opening as a new scenario, plus CSV export of any list.
- Round companion (`/rounds`, `POST /rounds/advice`): how each higher choice moved by the final round in recent years, and a Freeze / Float / Slide suggestion with its reason.
- Whole-course cost on the compare page, marked "at least" when hostel or mess charges aren't published.
- Ingest keeps every JoSAA round, and `--season-in-progress` keeps the current year out of the bands until its last round is published. Methodology shows the newest round on record.

## Product decisions without interviews (November 2026)
Family interviews weren't possible, so the four open questions were settled from public JoSAA behaviour (closing-rank patterns, counselling guides) and are checked against anonymous usage instead.
- **Default order:** guides and closing ranks show both habits are common: CSE anywhere over core at a top institute, and lower branches of top IITs over core at newer ones. So no single default is right. Onboarding now asks one question (branch first, balanced, institute first; balanced stays the default), and `onboarding_completed` counts the answers. If more than half pick branch first after 200 completions, make it the default.
- **List builder:** kept as is. A "check my list" mode (paste your own order, get flagged gaps and risky orderings) goes in the backlog after state counselling.
- **Round companion:** kept. Its advice already gives the reason in plain words. Revisit if `round_advice_viewed` shows mostly Float but families still ask what it means.
- **State counselling:** moved to the top of the backlog. A general-category student above CRL 1.5 lakh gets almost no JoSAA options, and those students are the majority of JEE Main takers.

## Backlog in recommended order
0. **First state counselling adapter** (one large state, cutoffs plus home-state rules), so students above CRL 1.5 lakh get a real list.
1. **Authentication and role-based access**, then saving profiles and lists on the server.
2. **Admin:** review queue, verification, audit trail. This also unlocks marking data `verified`.
3. **More branch-level reports and fees**, starting with MNNIT and PEC. Fee coverage (6 of 20 pilots) limits the calculator most.
4. Have a person review a sample of placement rows.
5. Side-by-side cost comparison.
6. Finish OpenAlex coverage, then curriculum and department-level faculty.
7. Intermediate rounds.
8. CSAB history as each year is published, then a first state adapter.
10. OCI/PIO and foreign candidate support.
11. Language model on top of the assistant's existing tools (needs an API key and approval for a paid service).
12. Rate limiting, security review, staging deployment.
13. End-to-end browser tests, and a server-generated PDF if browser printing isn't enough.
