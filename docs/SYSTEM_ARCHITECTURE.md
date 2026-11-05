# System architecture

## Repository assessment (2026-11-05)
`~/economet` is a non-git parent folder of unrelated products, with no admissions code. Threshold is therefore a new standalone project in `economet/threshold`. Sibling projects were not modified, except that two run configurations were added to `economet/.claude/launch.json`. Only stack versions and conventions were reused (Next 16, React 19, Recharts, zod).

## Current shape

```
Browser (Next.js, React, Tailwind, Recharts, react-hook-form, zod)
   |  /api/v1/* rewritten by Next to the backend
FastAPI  ->  services (eligibility, bands, scoring, recommend, comparison)  [pure rules, unit tested]
   |  SQLAlchemy, Alembic
PostgreSQL  <-  ingest (josaa_fetch -> raw files -> josaa_parse -> load)
```

- **All business logic is in the backend.** The frontend only displays results and validates input shape.
- **Rules are pure functions** in `app/services/eligibility.py`, `bands.py` and `scoring.py`. They touch no database, which makes them directly testable.
- **Raw and validated data are separate.** Raw HTML is in `data/raw/` (git-ignored). Validated rows are in Postgres, each linked to a `source_documents` row with its SHA-256.
- **Rank lists are a first-class field.** `cutoff_records.rank_list`, such as `JEE_MAIN:OBC-NCL`, must match the student's claim before any comparison happens.

## Multi-exam and multi-authority expansion
`cutoff_records.authority` and `rank_list` are not JEE-specific. Each new authority (CSAB, state CETs, later CAT or NEET) needs its own fetcher, parser and eligibility adapter. The current `eligibility.py` is the JoSAA adapter and will move behind a shared interface when the second authority is added. It is not generalised now because one implementation can't show what the interface should be.

## Stack differences from the brief

| Brief | Now | Reason |
|---|---|---|
| shadcn/ui | Small custom components in `components/ui.tsx` | No need yet for a full component library. Can be adopted later |
| pgvector | Not installed | Only needed for Phase 7 RAG. Requires installing the extension |
| Redis, workers | Not used | No background jobs yet. Ingestion is a CLI |
| Object storage | Local `data/raw` | Fine for local use; required before hosting |
| Auth, RBAC, rate limiting | **Not built** | Required before any public deployment |

## Technical risks

| Risk | Impact | Mitigation |
|---|---|---|
| JoSAA reuse terms are silent | Commercial use is uncertain | Attribute, and confirm with JoSAA before launch |
| JoSAA page layout changes | Ingestion breaks | Parser rejects unknown headers, and unknown institute names stop the load |
| NIRF blocks scripted access | No official rankings or graduate outcomes | Manual download and import. Access controls are not bypassed |
| Programme renames | Split histories | Programme identity is the raw name per institute. Merging needs a reviewed alias table (backlog) |
| Business rules change yearly | Wrong eligibility | Rules cite the 2026 document. Review each year before counselling |
| Sparse quality data | Quality score stays withheld | Reported openly. Collection is the top roadmap item |
