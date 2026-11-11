# API specification

Base path `/api/v1`. Interactive schema at `/docs` when the backend is running. Validation failures return 422 and unknown IDs return 404.

**There is no authentication, so the public deployment runs read-only and stores nothing a student enters.** It has a rate limit counted per server instance, and API docs are off. Add authentication and a shared limit before enabling any writes publicly.

## Built

| Method and path | Purpose |
|---|---|
| `GET /health` | Status and cutoff row count |
| `GET /meta` | States, branch families, career options, default weights, latest data year |
| `GET /institutions` | Filters: `q`, `type`, `state`, `branch`, `pilot`, `page`, `page_size` (up to 100) |
| `GET /institutions/{slug}` | Profile, aliases, rankings, quota states, programmes, completeness, and `careers`: branch outcomes, outcome mix, sectors, recruiters, alumni sample |
| `GET /programmes/{id}` | Programme, seats available, placements, ranking, fees |
| `GET /programmes/{id}/cutoffs` | `seat_type`, `quota`, `gender_pool`. Each row has `rank_list` and its source |
| `GET /programmes/{id}/placements` | Records, or status "Data not available" |
| `POST /recommendations/generate` | Shortlist |
| `GET /exams` | Routes beyond JEE, with sources and limits. A route with rounds lists them in order (`rounds`), and its groups end in ` · <round>` and are sorted by round. `default_group` and `default_programme` name the list the page opens on |
| `GET /exams/{code}` | Past figures for one route. A student's figure is compared only once a category is chosen, and a quota too where the route needs one. A record may carry `fee`: `title`, `note`, `declared` (label and value, word for word), `source_url`, `year` and `status` (`official` for KEA, `declared by the college` for MCC's fee forms) |
| `GET /exams/{code}/shortlist` | A student's seats on one route. Needs `value`, `category`, and `quota` (without the round) where the route needs one; optional `programme`, `gender`, `order` (`top` or `closest`) and `search`. Each seat has `rounds` (every round's figure, and whether it `reached` the student) and a `position`: `first_round`, `later_round`, `leftover_round` (stray, special or spot rounds), `reached` (routes with one cut-off) or `near` (beyond the student but within 20%, rank routes only). There are no bands, because a route covers one year. Seats also carry `ranking`, `fee`, `seats`, `why`, and `institution` with institute-wide faculty figures where the name exactly matches one JoSAA institute. Each position returns its first 100 |
| `POST /comparisons` | 2 to 4 distinct programme IDs, optional profile |
| `POST /preference-lists/analyse` | Checks an ordered list, and returns it in the same order |
| `POST /reports/parent` | Plain-language report for up to 8 programmes |
| `GET /financial/defaults/{programme_id}` | Published fee and newest median, or nulls |
| `POST /financial/roi` | Cost, loan and salary scenarios |
| `GET /data/sources` | Source registry |
| `GET /data/completeness` | Coverage counts and what is not yet collected |

### `POST /recommendations/generate`

```json
{
  "profile": {
    "category": "OBC-NCL",
    "gender": "female",
    "is_pwd": false,
    "eligibility_state": "Karnataka",
    "class12_status": "meets",
    "main": { "crl": 15000, "category_rank": 3000 },
    "advanced": {},
    "advanced_qualified": false,
    "preferred_branches": ["CS"],
    "avoid_branches": ["CIVIL"],
    "career_goals": ["software"],
    "priorities": { "branch_fit": 30, "reputation": 20 }
  },
  "per_band_limit": 25
}
```

The response has `options`, `counts` by band, `excluded`, `warnings`, `data_year`, `history_window`, `engine_version` and `result_hash`. Each option has `band`, `best_route`, `other_routes`, `quality`, `suitability`, `ranking`, `placements`, `fee`, `strengths`, `weaknesses`, `data_gaps` and `why`.

Contradictory input is rejected, for example a category rank for GEN, a PwD rank without PwD status, Advanced ranks without qualifying, or a branch both preferred and avoided.

Responses contain no probability fields, and a test enforces that.

## Planned
`POST /students/profile`, `POST /admissions/predict`, `GET /programmes/{id}/faculty`, `POST /preference-lists` (saving on the server), `POST /ai/counselling`, `GET /admin/ingestion-jobs`.

## Counselling assistant
`POST /api/v1/ai/counselling` with `{"question": "...", "profile": {...}}`. `profile` is optional, and the question isn't stored.

Returns `tool`, `summary`, `facts` (each with `text`, `source_title`, `source_url`, `year`, `verification_status`), `reasoning` (general reasoning, not data), `gaps`, `needs_profile` and `uses_ai_model`, which is always `false`. A question matches one fixed tool, and there is no free-form database access.

## Faculty
`GET /api/v1/programmes/{id}/faculty` returns `institute_wide` figures and a `department_level` that is always `null`, because none is collected.

