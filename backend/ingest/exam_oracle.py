"""Independent checks across exams and ranks, recomputed from raw data rather than app logic.

Run from backend/: .venv/bin/python ingest/exam_oracle.py
"""
import json,os,sqlite3,sys,time,collections
from pathlib import Path
B=Path.cwd(); db=B/"snapshot/threshold.db"
os.environ.update(DATABASE_URL=f"sqlite:///file:{db}?mode=ro&immutable=1&uri=true",ENVIRONMENT="production",READ_ONLY="true",RATE_LIMIT_PER_MINUTE="1000000")
sys.path.insert(0,".")
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.schemas import StudentProfile
from app.services.recommend import generate,lineage_map,offered_programmes
from app.services.scoring import DEFAULT_PRIORITIES
c=TestClient(app); fails=collections.Counter(); ex=collections.defaultdict(list)
def fail(k,info):
    fails[k]+=1
    if len(ex[k])<4: ex[k].append(info)
# ---------- demo routes
data=json.load(open("snapshot/exam_routes.json"))
LEVELS={"neet-ug":[1,50,100,500,1000,5000,10000,20000,50000,100000,300000,1000000,2000000],"clat":[1,50,100,120,121,500,1000,3142,5000,10000,30000],"gate-ccmt":[100,250,300,345,400,500,577,600,700,1000],"maharashtra-engineering":[0.01,10,30,50,60,70,80,88.5013511,90,95,99,99.9,100]}
n=0
print("=== DEMO ROUTES")
for r in data["routes"]:
    code=r["code"]; low=r["metric"]["lower_is_better"]; cats=sorted({x["category"] for x in r["records"]})
    for cat in cats:
      needs_group=r.get("compare_requires_group")
      for grp in (sorted({x["group"] for x in r["records"] if x["category"]==cat}) if needs_group else [None]):
        prev=None
        for v in LEVELS[code]:
            q={"value":v,"category":cat,"limit":200}
            if grp: q["group"]=grp
            res=c.get(f"/api/v1/exams/{code}",params=q).json(); n+=1
            if not res["compared"]: fail("demo not compared",(code,cat,grp,v))
            if grp and any(x["group"]!=grp for x in res["records"]): fail("demo quota leak",(code,cat,grp,v))
            usable=[x for x in r["records"] if x["category"]==cat and x["value"] is not None and (not grp or x["group"]==grp)]
            want=[x for x in usable if (x["value"]>=v if low else x["value"]<=v)]
            if res["matched"]!=len(want) or res["total"]!=len(usable): fail("demo count",(code,cat,v,res["matched"],len(want)))
            if any(x["category"]!=cat for x in res["records"]): fail("demo category leak",(code,cat,v))
            if any(not (x["value"]>=v if low else x["value"]<=v) for x in res["records"]): fail("demo wrong inclusion",(code,cat,v))
            st=[x["standing"] for x in res["records"]]
            if st!=sorted(st,reverse=True): fail("exam top order",(code,cat,v))
            close=c.get(f"/api/v1/exams/{code}",params={**q,"order":"closest"}).json()["records"]
            vals=[x["value"] for x in close]
            if vals!=sorted(vals,reverse=not low): fail("exam closest order",(code,cat,v))
            if prev is not None and (res["matched"]>prev if low else res["matched"]<prev): fail("demo monotonic",(code,cat,v,prev,res["matched"]))
            prev=res["matched"]
    # across-category comparison must never happen
    res=c.get(f"/api/v1/exams/{code}",params={"value":LEVELS[code][3]}).json()
    if res["compared"]: fail("demo compared without category",code)
    if needs_group_any:=r.get("compare_requires_group"):
        res=c.get(f"/api/v1/exams/{code}",params={"value":LEVELS[code][3],"category":cats[0]}).json()
        if res["compared"]: fail("demo compared without quota",code)
print("demo queries",n)
print("\n--- what each route shows first")
SHOW={"neet-ug":[("Open","MBBS",[1,100,1000,10000,50000,200000]),("OBC","MBBS",[1000,50000]),("SC","MBBS",[5000,150000]),("ST","MBBS",[50000])],"clat":[("General (General)",None,[50,120,121]),("Other Backward Class (OBC)",None,[500,1177,1178])],"gate-ccmt":[("OPEN",None,[400,600,800]),("EWS",None,[340])],"maharashtra-engineering":[("GOPENS",None,[99.9,99,95,90,70,40]),("LOBCS",None,[90]),("TFWS",None,[97]),("EWS",None,[95])]}
for code,rows in SHOW.items():
    for cat,s,vals in rows:
        for v in vals:
            p={"value":v,"category":cat,"limit":4}
            if s:p["search"]=s
            if code=="neet-ug":p["group"]="All India"
            res=c.get(f"/api/v1/exams/{code}",params=p).json()
            print(f" {code} {cat} {v}: {res['matched']}/{res['total']}", [f"{x['value']} {x['institute'][:26]}|{x['programme'][:18]}" for x in res['records'][:3]])
print("\n--- edge inputs")
for code,params in [("clat",{"value":0}),("clat",{"value":-5}),("clat",{"value":"abc"}),("nope",{}),("neet-ug",{"value":1.5,"category":"Open"}),("maharashtra-engineering",{"value":150,"category":"GOPENS"}),("gate-ccmt",{"value":5000,"category":"OPEN"}),("neet-ug",{"value":99999999,"category":"Open"}),("clat",{"category":"Bogus","value":5}),("clat",{"category":"' OR 1=1 --"}),("neet-ug",{"search":"zzzz"}),("neet-ug",{"limit":0}),("neet-ug",{"limit":1000})]:
    x=c.get(f"/api/v1/exams/{code}",params=params); b=x.json() if x.status_code==200 else {}
    print(" ",code,params,x.status_code,{k:b.get(k) for k in("matched","total")} if b else "")
# ---------- JEE
print("\n=== JEE")
con=sqlite3.connect(f"file:{db}?mode=ro&immutable=1",uri=True); con.row_factory=sqlite3.Row
S=SessionLocal(); lineage=lineage_map(S)
rows=con.execute("select p.branch_family fam,c.programme_id pid,c.year,c.quota,c.seat_type,c.gender_pool,c.closing_rank,c.rank_list,c.is_preparatory,p.required_paper,i.institute_type t,i.short_name n,i.id iid from cutoff_records c join programmes p on p.id=c.programme_id join institutions i on i.id=p.institution_id where c.is_final_round=1 and c.closing_rank is not null and c.is_preparatory=0").fetchall()
Y=max(r["year"] for r in rows); hist=collections.defaultdict(list)
for r in rows:
    if r["year"]>Y-3: hist[(lineage.get(r["pid"],r["pid"]),r["quota"],r["seat_type"],r["gender_pool"])].append(r)
qs=collections.defaultdict(lambda:collections.defaultdict(set))
for iid,q,st in con.execute("select institution_id,quota,state from quota_eligible_states"): qs[iid][q].add(st)
offered=offered_programmes(S,Y)
seats={(a,b,c_,d):e for a,b,c_,d,e in con.execute("select programme_id,quota,seat_type,gender_pool,seats from seat_matrix_records where year=?",(Y,))}
SEAT={"GEN":None,"GEN-EWS":"EWS","OBC-NCL":"OBC-NCL","SC":"SC","ST":"ST"}
def band(rank,cl):
    if len(cl)<2:
        return "beyond" if rank>1.2*cl[0] else None
    lo,hi=min(cl),max(cl)
    return "safer" if rank<=0.9*lo else "competitive" if rank<=hi else "ambitious" if rank<=1.2*hi else "beyond"
def expected(prof,catrank_main,catrank_adv):
    pools=["neutral","female"] if prof["gender"]=="female" else ["neutral"]
    out=collections.defaultdict(dict)
    for (pid,q,seat,pool),rs in hist.items():
        r0=rs[0]; adv=r0["t"] in("IIT","IISC")
        if r0["fam"]=="ARCH": continue
        if pool not in pools or r0["required_paper"]!=("advanced" if adv else "main_paper1"): continue
        ranks=prof["advanced"] if adv else prof["main"]
        if adv and not prof["advanced_qualified"]: continue
        if seat=="OPEN": rk=ranks.get("crl")
        elif seat==SEAT[prof["category"]]: rk=ranks.get("category_rank")
        else: rk=None
        if rk is None: continue
        if q!="AI":
            if adv: continue
            st=prof["eligibility_state"]; h=qs[r0["iid"]]
            home=set().union(*[h.get(k,set()) for k in("HS","GO","JK","LA")])
            if q=="OS":
                if not home or st in home: continue
            elif st not in h.get(q,set()): continue
        cl=[x["closing_rank"] for x in rs]; yrs=[x["year"] for x in rs]
        if seats.get((pid,q,seat,pool))==0 and Y not in yrs: continue
        out[pid][(q,seat,pool)]=(band(rk,cl),rk,min(cl),max(cl))
    return {p:v for p,v in out.items() if any(b[0]!="beyond" for b in v.values()) and p in offered}
per={}
ADV=[1,50,100,500,1000,2500,5000,10000,20000,50000]; MAIN=[100,1000,5000,10000,20000,50000,100000,200000,500000,1000000]
cases=[]
for cat,div in [("GEN",1),("GEN-EWS",8),("OBC-NCL",3),("SC",10),("ST",40)]:
    for st,g in [("Uttar Pradesh","male"),("Kerala","female"),("Maharashtra","male")]:
        for a in ADV: cases.append(dict(cat=cat,div=div,st=st,g=g,adv=a,main=None))
        for m in MAIN: cases.append(dict(cat=cat,div=div,st=st,g=g,adv=None,main=m))
    for a,m in [(1000,3000),(5000,20000),(20000,60000)]: cases.append(dict(cat=cat,div=div,st="Uttar Pradesh",g="male",adv=a,main=m))
t=time.time(); seen={}; tot=0
for k in cases:
    mk=lambda v:(None if v is None else ({"crl":v} if k["cat"]=="GEN" else {"crl":v,"category_rank":max(1,v//k["div"])}))
    prof=dict(category=k["cat"],gender=k["g"],eligibility_state=k["st"],class12_status="meets",main=mk(k["main"]) or {},advanced=mk(k["adv"]) or {},advanced_qualified=bool(k["adv"]),priorities=DEFAULT_PRIORITIES)
    res=generate(S,StudentProfile(**prof),per_band_limit=10**6,record_run=False); opts=res["options"]; tot+=len(opts)
    exp=expected(prof,None,None); got={o["programme_id"]:o for o in opts}
    excl=res["excluded"]
    for p in set(exp)-set(got):
        if not any(True for _ in [0]) : pass
        fail("JEE missing option",(k["cat"],k["st"],k["adv"],k["main"],p))
    for p in set(got)-set(exp): fail("JEE extra option",(k["cat"],k["st"],k["adv"],k["main"],p,got[p]["programme"]))
    for p,o in got.items():
        if o["branch_family"]=="ARCH": fail("JEE architecture shown",(k["cat"],k["adv"],p))
        b=o["best_route"]; e=exp.get(p,{}).get((b["quota"],b["seat_type"],b["gender_pool"]))
        if e is None: fail("JEE route not eligible",(k["cat"],k["st"],k["adv"],k["main"],p,b["quota"],b["seat_type"])); continue
        if o["band"]!=e[0]: fail("JEE wrong band",(k["cat"],k["adv"],k["main"],p,o["band"],e))
        if b["rank_used"]!=e[1]: fail("JEE wrong rank list",(k["cat"],p,b["rank_used"],e[1]))
        inst=o["institution"]["type"]
        if not k["adv"] and inst in("IIT","IISC"): fail("JEE IIT for Main-only",(k["cat"],k["main"],p))
        if not k["main"] and inst not in("IIT","IISC"): fail("JEE NIT for Advanced-only",(k["cat"],k["adv"],p))
    banded=[o["standing"] for o in opts if o["band"]]
    if banded!=sorted(banded,reverse=True): fail("JEE order",(k["cat"],k["adv"],k["main"]))
    lim=[o for o in opts if not o["band"]]
    if any(o["band"] for o in opts[len(banded):]): fail("JEE limited not last",(k["cat"],k["adv"],k["main"]))
    seen[(k["cat"],k["st"],k["g"],k["adv"],k["main"])]={p:o["band"] for p,o in got.items()}
print("personas",len(cases),"options checked",tot,"secs",round(time.time()-t))
# monotonic: a better rank must keep every reachable option
for (cat,st,g,a,m),cur in seen.items():
    if a is None and m is None: continue
    if a and m: continue
    ladder=ADV if a else MAIN; v=a or m; i=ladder.index(v)
    if i==0: continue
    better=seen[(cat,st,g,ladder[i-1],None) if a else (cat,st,g,None,ladder[i-1])]
    for p in cur:
        if p not in better: fail("JEE better rank loses option",(cat,st,g,v,ladder[i-1],p))
print("\n--- JEE top of list (General, UP, no preference)")
for label,prof in [("Adv",dict(advanced={"crl":v},advanced_qualified=True)) for v in ADV]+[("Main",dict(main={"crl":v})) for v in MAIN]+[("Adv+Main",dict(advanced={"crl":3000},advanced_qualified=True,main={"crl":8000}))]:
    res=generate(S,StudentProfile(category="GEN",gender="male",eligibility_state="Uttar Pradesh",class12_status="meets",priorities=DEFAULT_PRIORITIES,**prof),record_run=False)
    v=(prof.get("advanced") or prof.get("main"))["crl"]
    print(f" {label} {v}: {dict(res['counts'])}"); print("    ",[f"{(o['band'] or 'ltd')[:3]} {o['institution']['short_name']} {o['programme'][:26]}" for o in res["options"][:4]])
print("\n=== FAILS",dict(fails) or "none")
for k,v in ex.items(): print(" ",k,v)
