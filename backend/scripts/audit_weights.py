# Run against the real snapshot: PYTHONPATH=. DATABASE_URL=sqlite:///snapshot/threshold.db READ_ONLY=true python3 scripts/audit_weights.py
"""Audit the two list orders and the suitability weights on real data."""
import json, statistics
from itertools import combinations
from app.db import SessionLocal
from app.schemas import StudentProfile
from app.services import recommend as rec
from app.services.scoring import DEFAULT_PRIORITIES

def P(**kw):
    base = dict(category="GEN", gender="male", eligibility_state="Uttar Pradesh", class12_status="meets", main={"crl": None}, advanced={}, advanced_qualified=False)
    base.update(kw); return StudentProfile(**base)

def spearman(a, b):
    n = len(a)
    if n < 3: return None
    ra = {x: i for i, x in enumerate(sorted(range(n), key=lambda i: a[i]))}
    rb = {x: i for i, x in enumerate(sorted(range(n), key=lambda i: b[i]))}
    d = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return round(1 - 6 * d / (n * (n * n - 1)), 3)

def kendall_top(base, other, k=20):
    """Share of pairs among the baseline top-k kept in the same order."""
    top = base[:k]; pos = {p: i for i, p in enumerate(other)}
    pairs = [(x, y) for x, y in combinations(top, 2) if x in pos and y in pos]
    if not pairs: return None
    return round(sum(1 for x, y in pairs if pos[x] < pos[y]) / len(pairs), 3)

CASES = {
    "A: 15k, wants CS/ECE, software": P(main={"crl": 15000}, preferred_branches=["CS", "AI_DS", "ECE"], acceptable_branches=["EE", "MATH_COMP"], career_goals=["software"]),
    "B: 15k, no preferences": P(main={"crl": 15000}),
    "C: 45k, wants CS, prefers UP": P(main={"crl": 45000}, preferred_branches=["CS", "AI_DS"], acceptable_branches=["ECE", "EE"], preferred_states=["Uttar Pradesh"], career_goals=["software"]),
    "D: Adv 4000, wants CS/MnC": P(main={"crl": 16000}, advanced={"crl": 4000}, advanced_qualified=True, preferred_branches=["CS", "MATH_COMP", "AI_DS"], acceptable_branches=["ECE", "EE"]),
    "E: 70k, core, budget 2L": P(main={"crl": 70000}, preferred_branches=["ME", "CIVIL", "EE"], career_goals=["core"], annual_budget_inr=200000),
}
out = {}
with SessionLocal() as db:
    for name, prof in CASES.items():
        res = {}
        for order in ("top", "fit"):
            r = rec.generate(db, prof, per_band_limit=100000, record_run=False, order=order)
            res[order] = [o for o in r["options"] if o["band"]]
        fit, top = res["fit"], res["top"]
        pref = set(prof.preferred_branches); acc = set(prof.acceptable_branches)
        def tier(o): return 2 if o["branch_family"] in pref else 1 if o["branch_family"] in acc else 0
        def violations(lst):
            v = 0; worst = None
            for i, o in enumerate(lst):
                for later in lst[i+1:i+200]:
                    if tier(later) > tier(o) and pref:
                        v += 1
            return v
        demand = lambda o: next((c["score"] for c in o["suitability"]["components"] if c["key"] == "demand"), None)
        has_place = lambda o: any(c["key"] == "placements" and c["score"] is not None for c in o["suitability"]["components"])
        n = len(fit)
        top20 = fit[:20]
        out[name] = {
            "options": n,
            "fit_top10": [f"{o['institution']['short_name']} | {o['branch_label']} | {o['band'][:4]} | fit {o['suitability']['score']}" for o in fit[:10]],
            "top_top10": [f"{o['institution']['short_name']} | {o['branch_label']} | {o['band'][:4]} | stand {o['standing']}" for o in top[:10]],
            "fit_branch_order_violations": violations(fit) if pref else None,
            "top_branch_order_violations": violations(top) if pref else None,
            "fit_vs_demand_spearman": spearman([-(o["suitability"]["score"] or 0) for o in fit], [-(demand(o) if demand(o) is not None else 50) for o in fit]),
            "top_vs_demand_spearman": spearman([-o["standing"] for o in top], [-(demand(o) if demand(o) is not None else 50) for o in top]),
            "fit_top20_with_placement_data": sum(1 for o in top20 if has_place(o)),
            "all_with_placement_data_share": round(sum(1 for o in fit if has_place(o)) / max(1, n), 2),
            "fit_top20_bands": {b: sum(1 for o in top20 if o["band"] == b) for b in ("safer", "competitive", "ambitious")},
        }
        # Sensitivity: change one weight at a time by -50% and +50%.
        base_ids = [o["programme_id"] for o in fit]
        sens = {}
        for key in DEFAULT_PRIORITIES:
            if DEFAULT_PRIORITIES[key] == 0: continue
            for f in (0.5, 1.5):
                pr = dict(DEFAULT_PRIORITIES); pr[key] = DEFAULT_PRIORITIES[key] * f
                p2 = prof.model_copy(update={"priorities": pr})
                r2 = rec.generate(db, p2, per_band_limit=100000, record_run=False, order="fit")
                ids2 = [o["programme_id"] for o in r2["options"] if o["band"]]
                sens[f"{key} x{f}"] = {"pair_order_kept_top20": kendall_top(base_ids, ids2), "top10_overlap": len(set(base_ids[:10]) & set(ids2[:10]))}
        out[name]["sensitivity"] = sens
json.dump(out, open("/tmp/weights.json", "w"), indent=1)
for name, d in out.items():
    print("\n==", name, "options", d["options"])
    print(" fit top10:"); [print("   ", x) for x in d["fit_top10"]]
    print(" top top10:"); [print("   ", x) for x in d["top_top10"][:6]]
    for k in ("fit_branch_order_violations", "top_branch_order_violations", "fit_vs_demand_spearman", "top_vs_demand_spearman", "fit_top20_with_placement_data", "all_with_placement_data_share", "fit_top20_bands"):
        print(f"  {k}: {d[k]}")
    worst = sorted(d["sensitivity"].items(), key=lambda kv: kv[1]["pair_order_kept_top20"] or 1)[:4]
    print("  most sensitive:", worst)
