# Development roadmap

The brief's phases were reordered slightly. Its first vertical slice crosses Phases 1, 3, 5 and 6, so parts of each are done.

| Phase | Scope | Status |
|---|---|---|
| 0 | Inspection, architecture, docs | **Done** |
| 1 | Database, auth, master data, admin foundation | **Partial**: database and master data done. Auth and admin not built |
| 2 | Source registry, imports, verification | **Partial**: registry, JoSAA ingestion, NIRF PDF extraction and validated CSV import done. Excel, review queue not built |
| 3 | Admission intelligence | **Mostly done** for JoSAA. Seat matrix not built |
| 4 | Placements, faculty, fees, finance | **Partial**: placements, recruiters, sectors, an alumni sample, fees and the calculator are in. Faculty and curriculum aren't |
| 5 | Decision engine | **Partial**: suitability, bands, comparison done. Quality awaits data |
| 6 | User experience | **Partial**: 11 of the 15 sections built |
| 7 | AI counselling | Not started |
| 8 | Reports, PDF export | **Partial**: parent report and preference list save through browser printing. Feature access controls not started |
| 9 | Hardening and deployment | Not started |

## Sections from the brief (section 6)
Built: landing, onboarding, discovery, college profile, programme profile, comparison, recommendations, methodology, preference list, financial calculator, parent report. Admission prediction is part of recommendations.

Not built: student dashboard, AI assistant, admin dashboard.

## Backlog in recommended order
1. **Authentication and role-based access**, then saving profiles and lists on the server.
2. **Admin:** review queue, verification, audit trail. This also unlocks marking data `verified`.
3. **More branch-level reports and fees**, starting with MNNIT and PEC. Fee coverage (6 of 20 pilots) limits the calculator most.
4. Have a person review a sample of placement rows.
5. Side-by-side cost comparison.
6. Faculty data and OpenAlex research metrics, then curriculum.
7. Seat matrix, and intermediate rounds.
8. CSAB adapter, then a first state adapter.
9. Programme alias table for renames.
10. OCI/PIO and foreign candidate support.
11. RAG assistant with structured tools (needs an LLM key and `pgvector`).
12. Rate limiting, security review, staging deployment.
13. End-to-end browser tests, and a server-generated PDF if browser printing isn't enough.
