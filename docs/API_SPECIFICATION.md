# API specification

Base path `/api/v1`. Interactive schema at `/docs` when the backend is running. Validation failures return 422 and unknown IDs return 404.

**There is currently no authentication or rate limiting. Don't expose this API publicly until both exist.**

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
