# Run against the real snapshot: PYTHONPATH=. DATABASE_URL=sqlite:///snapshot/threshold.db READ_ONLY=true python3 scripts/audit_rank_sweep.py
"""Run the shortlist engine on the real snapshot across many profiles and check invariants."""
import json, time, sys
from collections import Counter
from sqlalchemy import select
from app.db import SessionLocal
from app.models import QuotaEligibleState, Institution
from app.schemas import StudentProfile
from app.services import recommend as rec

def P(**kw):
    base = dict(category="GEN", gender="male", eligibility_state="Uttar Pradesh", class12_status="meets", main={"crl": None}, advanced={}, advanced_qualified=False)
    base.update(kw)
    return StudentProfile(**base)

MAIN = [300, 1000, 3000, 6000, 10000, 15000, 25000, 40000, 60000, 90000, 150000, 250000, 400000, 700000, 1000000]
ADV = [50, 300, 1000, 3000, 7000, 12000, 20000, 30000]
profiles = []
for r in MAIN:
    profiles.append((f"GEN male UP main {r}", P(main={"crl": r})))
for r in ADV:
    profiles.append((f"GEN male UP adv {r} (main {r*4})", P(main={"crl": r * 4}, advanced={"crl": r}, advanced_qualified=True)))
for state in ["Karnataka", "Maharashtra", "Rajasthan", "West Bengal", "Bihar", "Goa", "Jammu and Kashmir", "Delhi"]:
    profiles.append((f"GEN male {state} main 30000", P(eligibility_state=state, main={"crl": 30000})))
profiles += [
    ("GEN female UP main 30000", P(gender="female", main={"crl": 30000})),
    ("OBC male UP crl 60000 cat 15000", P(category="OBC-NCL", main={"crl": 60000, "category_rank": 15000})),
    ("OBC male UP crl 60000 no cat rank", P(category="OBC-NCL", main={"crl": 60000})),
    ("SC female Bihar crl 300000 cat 9000", P(category="SC", gender="female", eligibility_state="Bihar", main={"crl": 300000, "category_rank": 9000})),
    ("ST male Odisha crl 500000 cat 3000", P(category="ST", eligibility_state="Odisha", main={"crl": 500000, "category_rank": 3000})),
    ("EWS male Rajasthan crl 40000 cat 6000", P(category="GEN-EWS", eligibility_state="Rajasthan", main={"crl": 40000, "category_rank": 6000})),
    ("GEN PwD UP crl 200000 crl_pwd 1500", P(is_pwd=True, main={"crl": 200000, "crl_pwd": 1500})),
    ("Class XII not met", P(class12_status="does_not_meet", main={"crl": 10000})),
]

with SessionLocal() as db:
    home = {}
    for q in db.scalars(select(QuotaEligibleState)):
        home.setdefault((q.institution_id, q.quota), set()).add(q.state)
    insts = {i.slug: i for i in db.scalars(select(Institution))}
    rows, problems = [], []
    for name, prof in profiles:
        t = time.time()
        res = rec.generate(db, prof, per_band_limit=100000, record_run=False, order="top")
        dt = time.time() - t
        counts = Counter(o["band"] or "limited" for o in res["options"])
        for o in res["options"]:
            r = o["best_route"]; inst = insts[o["institution"]["slug"]]
            if inst.institute_type in ("IIT", "IISC") and not prof.advanced_qualified:
                problems.append((name, "IIT without Advanced", o["programme_id"]))
            if r["gender_pool"] == "female" and prof.gender != "female":
                problems.append((name, "female pool for non-female", o["programme_id"]))
            if r["quota"] in ("HS", "GO", "JK", "LA") and prof.eligibility_state not in home.get((inst.id, r["quota"]), set()):
                problems.append((name, f"home quota {r['quota']} outside home state", o["institution"]["short_name"]))
            if r["rank_list"].endswith(":CRL") and r["seat_type"] != "OPEN":
                problems.append((name, "CRL used for category seat", o["programme_id"]))
            if r["seat_type"] != "OPEN" and prof.category == "GEN" and "PwD" not in r["seat_type"]:
                problems.append((name, "GEN student on category seat", r["seat_type"]))
            if o["band"] == "safer" and r["rank_used"] > 0.9 * (r["low_closing"] or 0):
                problems.append((name, "safer but not 10% inside", o["programme_id"]))
            if o["band"] == "competitive" and r["rank_used"] > (r["high_closing"] or 0):
                problems.append((name, "competitive beyond worst closing", o["programme_id"]))
        rows.append({"profile": name, "safer": counts["safer"], "competitive": counts["competitive"], "ambitious": counts["ambitious"], "limited": counts["limited"],
                     "excluded": res.get("excluded"), "seconds": round(dt, 2),
                     "top5": [f"{o['institution']['short_name']} {o['branch_label']} [{(o['band'] or 'ltd')[:4]}]" for o in res["options"][:5]],
                     "warnings": res["warnings"][:2]})
    # Monotonicity: a programme Safer at a worse rank must be Safer or listed at a better rank.
    mono = []
    prev = None
    for r in MAIN:
        res = rec.generate(db, P(main={"crl": r}), per_band_limit=100000, record_run=False)
        safer = {o["programme_id"] for o in res["options"] if o["band"] == "safer"}
        allp = {o["programme_id"]: o["band"] for o in res["options"]}
        if prev is not None:
            lost = [pid for pid in prev[1] if pid not in allp]
            mono.append((prev[0], r, len(lost)))
        prev = (r, safer)
json.dump({"rows": rows, "problems": problems[:50], "problem_count": len(problems), "monotonic": mono}, open("/tmp/sweep.json", "w"), indent=1, default=str)
for row in rows:
    print(f"{row['profile'][:42]:42} S{row['safer']:4} C{row['competitive']:4} A{row['ambitious']:4} L{row['limited']:4} {row['seconds']}s | {row['top5'][:3]}")
print("problems:", len(problems), problems[:8])
print("monotonic (better->worse, safer lost entirely):", mono)
