# Data sourcing

The live registry is `data/registry/sources.yaml`, and it is shown on the Methodology page. Access was checked directly on 2026-11-05.

| Source | Status | Notes |
|---|---|---|
| JoSAA opening and closing ranks | **In use** | Public forms with no login or CAPTCHA. Archive offers 2016-2025, and a separate page has the current year |
| JoSAA Business Rules 2026 | **In use** | Read by hand to write the eligibility rules |
| JoSAA seat matrix 2026 | **In use** | All 1,038 programmes and 67,323 seats. The load stops unless rows add up to the page's own totals. Also the official home-state list |
| CSAB special rounds 2026 | **In use, apart** | Rounds 1 and 2, 715 programmes. The form offers the current year only, so there's no history and no bands. Foreign-candidate rows are left out |
| NIRF 2025 Engineering via Careers360 | **In use, secondary** | Ranks 1-50, 26 JoSAA institutes. Marked `secondary_unverified`. Press sources disagree on some scores |
| NIRF 2025 Engineering ranks 51-100, secondary copies | **In use, secondary** | 23 more JoSAA institutes, 49 in all. CorpReady agrees with all 26 ranks already held, and CollegeDekho gives the same order. Marked `secondary_unverified` |
| Manually entered locations | **In use, partly confirmed** | City and state for all 139 institutes. The seat matrix confirms the state for 40 (`state_official`). Cities and the other 99 stay `manual_unverified` |
| NIRF submissions on institute websites | **In use** | 67 institutes, 3 graduating years each. Self-reported and unaudited. Whole programme level, never a branch |
| Institute fee circulars | **In use** | 12 institutes for 2026-27, 4 with a complete yearly cost |
| Institute placement reports | **In use** | Branch-level: NIT Warangal (2 years), NIT Kurukshetra, IIT Guwahati, IIT (ISM). Definitions differ, so they aren't compared or scored |
| Wikidata | **In use, secondary** | Aggregate counts of documented people. No names stored. Not the alumni network |
| Faculty and academic tables in NIRF submissions | **In use** | 67 institutes. Totals only: names, ages and genders are read to count and are never stored. Whole submission, never a department |
| OpenAlex | **In use, partial** | 26 institutes, display only and never scored. The free daily budget ran out after 28 searches. `ingest.openalex_fetch` resumes where it stopped |
| LinkedIn and similar | **Rejected** | Scraping is prohibited and it holds restricted personal data |
| NIRF official | **Blocked for scripts** | Returned HTTP 403 to scripted requests. Not bypassed |
| JoSAA fee PDF | Rejected | The latest found is a *tentative* CSAB 2022 document, too old and uncertain to present as fees |
| IIT (BHU) 2026-27 fee notice | Rejected | It explicitly excludes first-semester students |
| Aggregator placement and fee figures | Rejected | Institute documents exist, and aggregators disagree with each other |
| NIRF 2026 rank lists on third-party sites | Rejected | Mostly SEO pages that disagree with each other and may repeat 2025. No trustworthy list was found |

## Pilot data collected (2026-11-05)

### Placements (177 rows, 59 institutes)
Each row is `All 4-year UG programmes`, stored with `scope=institution`. Each institute's document is listed in `data/registry/nirf_documents.yaml`.

| | Institutes |
|---|---:|
| Engineering submissions | 56 (45 from NIRF 2026, 11 from NIRF 2025) |
| Overall submissions, kept apart and not scored | 3 (IIT Roorkee, IIIT Bhagalpur, IIIT Dharwad) |
| Used in salary comparison after removing classes under 100 | 52 per year for 2023 and 2024 |
| Pilots covered | 18 of 20. **Missing:** IIIT Allahabad (links return 404), IIEST Shibpur (no recent document found) |

The table above is from the first collection. Eight more institutes were added on 2026-11-06 (see the gap review). **Other gaps:** 72 of 139 JoSAA institutes now have no data here. Sites that failed or showed no document include NIT Patna, Agartala, Raipur (TLS error), Puducherry, Manipur and Sikkim; IIT Patna, Indore, Gandhinagar, Jodhpur, Ropar, Jammu and Bhilai; and many newer IIITs and GFTIs. Their documents may exist. **Absence here doesn't mean an institute doesn't publish one.**

**Automatic checks, each of which keeps a document out if it fails:**
- The institute name printed in the document must match exactly, or match a reviewed exception in `nirf_name_overrides.yaml`. Fuzzy matching isn't used, because NIT names differ only by place.
- The document's stated year must be 2025 or later. This correctly rejected IIT Indore's file stored under a 2026 path, which is really from 2024.
- It must be an Engineering or Overall submission, with a table titled `UG [4 Years Program(s)]`.
- Each median in digits must agree with the same amount in words, allowing for misspellings.
- Placed students can't exceed graduating students, and medians must be in a plausible range.

**Reviewed exceptions:** the name list above, and one discrepancy in `nirf_reviewed_discrepancies.yaml`. IIT Guwahati's Engineering submission gives 21,60,000 in digits and 21.63 lakh in words for 2022-23. Its Overall submission gives 21,60,000 in both, so the digits are kept with a note on the row.

**Visual checks:** five tables were compared with the rendered page (IIT Bombay, BIT Mesra, MNNIT, NIT Nagaland, IIT Mandi). Not every document was read by eye.

**Not checked:** whether institutes reported accurately. NIRF figures are self-reported, and this project has not audited them. No second person has reviewed the rows, so they are `official` and not `verified`.

**Engineering and Overall differ.** They matched for IIT Bombay, IIT Kanpur and NIT Surathkal, but not for IIIT Jabalpur or IIT (BHU), probably because Overall covers more programmes. They are stored under separate reporting definitions and never compared.

### Branch-level placements, sectors and recruiters (47 rows, 8 sectors, 107 recruiters)
Transcribed by hand from the institutes' reports, because formats differ and one trap would have defeated a parser: NIT Warangal's 2024-25 table reads Median then Average, and its 2025-26 table reads Average then Median.

| Institute | Graduating | Measured against | Median published per branch |
|---|---|---|---|
| NIT Warangal | 2025, 2026 | Eligible students (CGPA at least 6.5 and took part in all drives), plus total students | Yes |
| NIT Kurukshetra | 2025 | Eligible students, plus offers | Yes |
| IIT Guwahati | 2025 | Registered students | Yes |
| IIT (ISM) Dhanbad | 2025 | Actively participating students | No, only for all B.Tech |

**Checks:** rows were added up and compared with each report's totals. NIT Warangal 2026: 660 plus 6 expected PPO conversions gives its 666. NIT Warangal 2025: 697. NIT Kurukshetra: 676 placed, 787 eligible. IIT (ISM): 632. IIT Guwahati's registered students add up to 842, but its placed figures disagree in its own report: branches sum to 634, its summary says 637 and its salary table 632. That's recorded on those rows.

**Left out:** BIT Mesra (charts without counts or medians, so values would have to be estimated), NIT Tiruchirappalli (rates only), MNNIT and PEC (not yet read).

**Sectors:** IIT (ISM) only, because IIT Guwahati's are in a chart without counts. **Recruiters:** IIT Guwahati only, read from logos in its 2024-25 report, leaving out unclear ones. A listing doesn't show how many were hired or from which branch.

**Recent placements don't measure the alumni network.** They show where new graduates were hired. Nothing here tracks careers over time.

### Alumni sample (Wikidata)
Counts people who list an institute as alma mater, by occupation and employer. Institutes are matched only on an exact name (`data/registry/wikidata_institutions.yaml`), which gave 24 institutes. Samples under 30 aren't shown, leaving 15: 13 IITs, VNIT Nagpur and IIIT Allahabad. So this section is mostly absent for NITs and other institutes, and the matches haven't been individually reviewed. IIT Bombay's sample was dominated by researchers (597 of 906), and no degree level is recorded, so this mostly reflects academic and PhD careers. Names and person identifiers aren't stored.

### Fees (6 institutes, 2026-27, new entrants)
IIT Bombay, Madras, Delhi and Roorkee; NIT Warangal and Calicut. All are for General/OBC-NCL/EWS students with family income above Rs 5 lakh, transcribed by hand. Totals were checked against each document's stated total.

Only IIT Roorkee publishes tuition, hostel and mess in one document, so it is the only one with a complete yearly cost. IIT Delhi has no yearly figures because its circular doesn't state which charges repeat.

**Missing:** IIT Kanpur (the linked file returns 404), Kharagpur, Hyderabad, BHU; NIT Tiruchirappalli (no 2026 B.Tech schedule found), Surathkal, Rourkela; MNNIT; all IIITs and GFTIs.

## Gap review (2026-11-06)
**Closed from official data**
- **Is a programme still offered?** The seat matrix lists exactly the 1,038 programmes with a 2026 cutoff, so a missing programme is now known to be off this year's list, not only suspected.
- **Home states.** The seat matrix prints them. They matched the earlier assumptions exactly for all 41 institutes with state quotas, including the ones flagged below, and they are now loaded from it.
- **Round count.** The current-year form offers 5 rounds for 2026 in November, so round 5 is the final one.

**Corrected by review**
- **Branch labels.** 20 programme names were in the wrong family, because a specialisation or second degree was matched first. Examples: E&ECE at IIT Kharagpur was Electrical, Industrial Chemistry was Mechanical, and ECE (Internet of Things) was CS.
- **Abu Dhabi.** IIT Delhi's four Abu Dhabi programmes now show their own location and don't inherit IIT Delhi's rank, fees or institute-wide placements.
- **Renames.** 22 renames in `programme_lineage.yaml` now share one history. Each pair runs in consecutive years with the same duration, and closing ranks moved by under about 30%. Seven doubtful pairs were left apart and are named in that file. Institutes haven't confirmed any of this.

**Reduced, still open**
| Gap | Before | Now | What would close it |
|---|---|---|---|
| NIRF rank on record | 26 institutes | 49 of 139 | Enter official ranks by hand. All 49 remain secondary. A rank says nothing about the 90 others, many of which may not take part |
| Placements | 59 institutes | 67 of 139 | Keep looking for submissions. 8 of the 67 were added on this date, and 3 of those are Overall submissions, which are shown but not scored |
| Fees | 6 institutes, 2 complete | 12, of which 4 complete | Institute circulars, mostly for hostel and mess. No IIIT or GFTI is covered |
| State confirmed | 0 | 40 of 139 | IITs and IIITs have no state quota, so they need a check against institute pages |

**Still not closed**
- **Quality score.** No option can reach the 50% evidence needed. Institute-wide placements and a NIRF rank reach 22.5%. Six of the eight dimensions have no data, and adding research counts from OpenAlex would still only reach about 40%. It should stay unscored until faculty and curriculum data exist. Filling it with proxies would look like knowledge we don't have.
- **Branch placements.** 38 of 1,143 programmes. Institutes rarely publish them, and the reports that do use different definitions.
- **Official NIRF ranks.** nirfindia.org still blocks scripts. This isn't bypassed, so a person needs to enter them.
- **State counselling and alumni outcomes.** Not collected.

**Known bias:** with a budget set, an institute that publishes its charges can lose points, while one that publishes nothing stays neutral. The default weight is small, but it can favour institutes with no published fees.

## Faculty and academic data (2026-11-06)
`ingest.nirf_academics` reads the tables in each accepted NIRF submission, then `ingest.load_academics` loads the totals.

**Checks**
- Faculty rows must be numbered without gaps. IIIT Guwahati's aren't, so it's shown with a note and left out of comparisons.
- A second count of current regular staff, taken directly from the document's text rather than its tables, matched all 67 documents.
- Funding amounts in digits must match the amount in words, or the amount is dropped. None disagreed.
- Where a table splits across pages, the amount is read from the document's text instead, and has no words check.

**Limits**
- Self-reported and unaudited, and not read line by line by a person.
- Whole institute only. No submission gives faculty by department, so `/programmes/{id}/faculty` always returns `department_level: null`.
- A student-faculty ratio uses regular staff only. IIIT Kota reports 10 regular staff out of 59 listed, so its 99 students per regular faculty member is what the document says, and it's shown beside the fuller count.
- Scores compare per-person figures across Engineering submissions with at least 20 regular faculty, and submissions may be a year apart.
- Nothing here measures teaching. The brief's named profiles, qualifications by person, Google Scholar and faculty-level publications aren't collected. They add personal data and aren't needed for anything shown.

**Counselling rules:** the assistant's answers on freeze, float, slide, withdrawal and fees summarise JoSAA's Business Rules of 1 June 2026, read by hand, with clause references. They need updating each year.

## What was fetched
Round 1 and the last round for each of 2021-2026, which is 12 tables and 132,982 rows. Each table takes one `ALL` query, with 2 seconds between requests and an identifying user agent.

```
python -m ingest.josaa_fetch --years 2021-2025 --current
python -m ingest.seat_matrix
python -m ingest.csab_fetch
python -m ingest.load
```

## Pipeline
1. **Fetch**: raw HTML goes to `data/raw/josaa`, with a JSON file recording URL, time and SHA-256.
2. **Parse**: `josaa_parse.py` rejects any table whose header has changed.
3. **Normalise**: names map through `institutions.yaml`. Unknown names stop the load, so no duplicate institutes are created.
4. **Load**: upserts are safe to re-run, and past records stay unchanged.

Built so far: JoSAA fetch and load, NIRF PDF extraction, and the CSV importer for placements and fees (see `data/import/README.md`). Not built: Excel import, general PDF extraction, review queues, scheduled refresh and the admin interface.

## Open items for a person to resolve
1. **JoSAA reuse rights.** The terms page neither allows nor forbids reuse. Ask JoSAA before commercial launch.
2. **Official NIRF rankings.** nirfindia.org still blocks scripts. Institute submissions now supply outcomes, but ranks still come from a secondary source. Someone needs to enter ranks from the official site. Also, look for the missing pilot submissions (IIIT Allahabad, IIEST Shibpur).
7. **Sample review of placement rows.** Have a person check a sample against the source PDFs, then mark checked rows `verified`.
6. **Location check.** Review all 139 cities, and the state of the 99 institutes the seat matrix doesn't confirm, starting with the 20 pilots.
8. **Programme renames.** Ask a person who knows JoSAA to review `programme_lineage.yaml`, and the pairs left out of it.
9. **CSAB reuse rights and rules.** As with JoSAA, reuse isn't addressed. Check CSAB eligibility rules before giving these leads more prominence.

## First 20 pilot institutions
Chosen to cover institution types, regions and a range of cutoffs. They get deeper data collection first. Cutoffs already cover all institutes.

- **IITs (8):** Bombay, Delhi, Madras, Kanpur, Kharagpur, Roorkee, Hyderabad, BHU Varanasi
- **NITs (6):** Tiruchirappalli, Surathkal, Warangal, Rourkela, Calicut, MNNIT Allahabad
- **IIITs (3):** IIIT Allahabad, ABV-IIITM Gwalior, IIITDM Jabalpur
- **GFTIs (3):** BIT Mesra, PEC Chandigarh, IIEST Shibpur

Their website addresses were entered from general knowledge and have not been individually verified.

## Scraping rules
Use only permitted access. Never bypass CAPTCHAs, logins or blocks. Don't collect restricted personal data. Keep raw documents apart from validated records.

## Routes beyond JEE
`/exams` shows past figures from official documents, with no bands or probabilities. Each route states its limits on the page.

| Route | Source | Status |
|---|---|---|
| NEET UG | MCC stray round allotment result, 2026 | Last rank allotted, calculated by us |
| CLAT UG | Consortium of NLUs, NLSIU fifth provisional list, 2026 | Official cut-off table, one university |
| GATE to NITs | CCMT 2025 score report | Official, 20 records for NIT Warangal |
| Maharashtra engineering | State CET Cell, CAP Round I, 2024-25 | Official, all institutes in that document |

By default each list puts top colleges first, as on the JEE shortlist: two parts official NIRF 2025 rank in the matching field (Medical for MBBS, Dental for BDS, Law, Engineering) to one part how contested the seat is within the same course, category and quota. Ranks come from `data/registry/nirf_2025_exam_routes.yaml`, read from nirfindia.org, and apply only where the counselling document names the same ranked institution. `python -m ingest.exam_rankings` attaches them and stops if any entry finds no institute. Students can switch to "Closest to my figure".

The project owner reports written confirmation from these authorities. Candidate identifiers, such as CLAT admit card numbers, are never stored.
