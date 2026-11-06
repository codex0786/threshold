"""Counselling assistant. Answers questions from stored records through a fixed list of tools.

There is no language model here and no free-form database access. A question is matched to one tool
by plain rules, and every figure in the answer comes from a stored record with its source. Facts,
general reasoning and gaps are returned separately, and the assistant never picks a winner.
"""
from __future__ import annotations

import re
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CutoffRecord, Institution, Programme
from app.schemas import StudentProfile
from app.services import comparison
from app.services import recommend as rec
from app.services.branches import FAMILY_LABELS
from app.services.scoring import MIN_GRADUATING_CLASS

RULES_URL = "https://josaa.nic.in/document/business-rule-3/"
RULES_TITLE = "JoSAA Business Rules 2026, published 1 June 2026"
LIMIT = 8
EXAMPLES = [
    "Should I choose NIT Trichy CSE or NIT Warangal ECE?", "Is an IIT lower branch better than an NIT top branch?",
    "Which colleges have the best placement consistency?", "Which colleges offer the best value under ₹10 lakh?",
    "What if I prioritise higher studies instead of placements?", "Which branch offers greater career flexibility?",
    "What is the difference between float and slide?", "Faculty and research at IIT Bombay",
]
# Everyday names that JoSAA's lists don't use.
NICKNAMES = {
    "nit trichy": "nit-tiruchirappalli", "nitt": "nit-tiruchirappalli", "nitk": "nit-surathkal", "nit karnataka": "nit-surathkal", "nitw": "nit-warangal",
    "iit kgp": "iit-kharagpur", "iit bhu": "iit-bhu", "bhu": "iit-bhu", "iit dhanbad": "iit-ism-dhanbad", "ism dhanbad": "iit-ism-dhanbad", "mnnit": "mnnit-allahabad",
    "nit allahabad": "mnnit-allahabad", "vnit": "vnit-nagpur", "nit nagpur": "vnit-nagpur", "svnit": "svnit-surat", "nit surat": "svnit-surat",
    "mnit": "mnit-jaipur", "nit jaipur": "mnit-jaipur", "manit": "manit-bhopal", "nit bhopal": "manit-bhopal", "bit mesra": "bit-mesra", "iiita": "iiit-allahabad",
}
BRANCH_WORDS = [
    (r"\b(ai|aiml|ai ml|artificial intelligence|data science|machine learning)\b", "AI_DS"),
    (r"\b(mnc|m and c|maths and computing|math and computing|mathematics and computing)\b", "MATH_COMP"),
    (r"\b(cse|cs|computer science|computer engineering|computers?|it|information technology)\b", "CS"),
    (r"\b(ece|electronics|communication)\b", "ECE"), (r"\b(eee|ee|electrical)\b", "EE"),
    (r"\b(mech|mechanical|me)\b", "ME"), (r"\b(civil)\b", "CIVIL"), (r"\b(chemical|chem)\b", "CHEM_E"),
    (r"\b(aerospace|aero)\b", "AERO"), (r"\b(metallurgy|metallurgical|materials|mining)\b", "MATERIALS"), (r"\b(biotech|biotechnology|bio)\b", "BIO"),
]
PROCESS = [
    (r"\bfreeze\b|\bfloat\b|\bslide\b", "Freeze, float and slide", 54, [
        "Freeze: you accept the offered seat and take no part in later rounds. The choice can't be changed later (clauses 48 and 52).",
        "Float: you accept the seat, and you'll take a higher choice at any institute if one is offered in a later round (clause 48).",
        "Slide: you accept the seat, and you'll take a higher choice only within the same institute (clause 48).",
        "If you get your first choice, only Freeze is available. Float and slide aren't available in the last round (clauses 48-50).",
        "You can move from float to slide or freeze, and from slide to freeze, in every round except the last (clause 51).",
        "If float or slide brings a higher choice and you reject it, you lose all seats and leave JoSAA 2026 (clause 48).",
    ]),
    (r"withdraw", "Withdrawing from a seat", 60, [
        "You can withdraw an IIT or IISc seat from round 2 up to the round before the last, and an NIT+ seat up to the final round (clause 63).",
        "Withdrawing ends your part in JoSAA 2026, and your seat acceptance fee is refunded less Rs 7,000 (clause 64).",
        "There is no spot or special round for IITs and IISc (clause 65).",
    ]),
    (r"\bexit\b", "Leaving without a seat", 62, [
        "A candidate with no allotted seat can exit from round 2 up to the round before the last. That ends eligibility for admission through JoSAA 2026 (clauses 68 and 69).",
    ]),
    (r"partial admission|\bpaf\b", "Partial admission fee", 59, [
        "NIT+ candidates holding a seat after round 5 pay this as well as the seat acceptance fee: Rs 20,000 for SC, ST and PwD category tags, and Rs 45,000 for others (clauses 59 and 60).",
        "It is adjusted against the institute's admission fee and isn't refundable. Not paying it forfeits the seat (clauses 60 and 62).",
    ]),
    (r"acceptance fee|seat fee", "Seat acceptance fee", 42, [
        "The fee is Rs 15,000 for SC, ST and PwD category tags, and Rs 30,000 for others, including Rs 5,000 processing charges (Section XVIII).",
        "It is paid once, in the round you first get a seat. If you later get another seat through float or slide, you don't pay again (clause 57).",
    ]),
    (r"\bcsab\b|special round|vacant seat", "CSAB special rounds", 60, [
        "Special rounds for vacant NIT+ seats aren't part of JoSAA. They are run by CSAB after JoSAA ends, under CSAB's own rules (clauses 65 and 67).",
        "A seat forfeited for not paying the partial admission fee goes into CSAB's special rounds (clause 62).",
    ]),
    (r"accept|report|document|step|what.*after.*allot|how.*confirm", "Accepting an allotted seat", 41, [
        "Accept the seat and choose freeze, slide or float, upload the required documents, then pay the seat acceptance fee (clause 42).",
        "Missing any online reporting step in that round's timeline cancels the seat and ends your part in later rounds (clause 41).",
        "See Annexure 3 of the Business Rules for each round's dates and documents.",
    ]),
]


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9₹. ]", " ", text.lower().replace("&", " and ")).split())


def _fact(text: str, title: str | None = None, url: str | None = None, year: int | str | None = None, status: str | None = None) -> dict:
    return {"text": text, "source_title": title, "source_url": url, "year": year, "verification_status": status}


def _answer(tool: str, summary: str, facts: list[dict] | None = None, reasoning: list[str] | None = None, gaps: list[str] | None = None, needs_profile: bool = False) -> dict:
    return {
        "tool": tool, "summary": summary, "facts": facts or [], "reasoning": reasoning or [], "gaps": gaps or [], "needs_profile": needs_profile,
        "uses_ai_model": False, "examples": EXAMPLES if tool == "not_understood" else [],
    }


def _inr(value: int | float | None) -> str:
    if value is None:
        return "not on record"
    if value >= 10_000_000:
        return f"Rs {value / 10_000_000:.2f} crore"
    return f"Rs {value / 100_000:.2f} lakh"


def find_institutions(db: Session, question: str) -> list[Institution]:
    """Institutes named in the question, in order of mention. Longest names win, so 'IIIT Allahabad' isn't read as something shorter."""
    text = f" {_norm(question)} "
    institutions = {i.slug: i for i in db.scalars(select(Institution).options(joinedload(Institution.aliases)).order_by(Institution.id)).unique()}
    names = {_norm(k): v for k, v in NICKNAMES.items()}
    for inst in institutions.values():
        names[_norm(inst.short_name)] = inst.slug
        for alias in inst.aliases:
            names[_norm(alias.alias)] = inst.slug
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for name in sorted(names, key=len, reverse=True):
        for match in re.finditer(rf" {re.escape(name)} ", text):
            span = (match.start() + 1, match.end() - 1)
            if not any(a < span[1] and span[0] < b for a, b in taken):
                taken.append(span)
                found.append((span[0], names[name]))
    seen, ordered = set(), []
    for _, slug in sorted(found):
        if slug not in seen and slug in institutions:
            seen.add(slug)
            ordered.append(institutions[slug])
    return ordered


def _branch_after(text: str, start: int, end: int) -> str | None:
    window = text[start:end]
    hits = [(m.start(), family) for pattern, family in BRANCH_WORDS for m in re.finditer(pattern, window)]
    return min(hits)[1] if hits else None


def _pairs(db: Session, question: str, institutions: list[Institution]) -> list[tuple[Institution, str | None]]:
    """Each institute with the branch named between it and the next institute."""
    text = _norm(question)
    points = []
    for inst in institutions:
        names = sorted({_norm(inst.short_name), *(_norm(a.alias) for a in inst.aliases), *(_norm(k) for k, v in NICKNAMES.items() if v == inst.slug)}, key=len, reverse=True)
        at = min((text.find(n) for n in names if text.find(n) >= 0), default=0)
        length = next((len(n) for n in names if text.find(n) == at), 0)
        points.append((at, at + length, inst))
    points.sort(key=lambda p: p[0])
    out = []
    for i, (_, end, inst) in enumerate(points):
        stop = points[i + 1][0] if i + 1 < len(points) else len(text)
        out.append((inst, _branch_after(text, end, stop)))
    return out


def _programme(db: Session, inst: Institution, family: str | None, data_year: int) -> tuple[Programme | None, int]:
    """The plainest 4-year main-campus programme in the family, and how many others there are."""
    if family is None:
        return None, 0
    offered = rec.offered_programmes(db, data_year)
    rows = [p for p in db.scalars(select(Programme).options(joinedload(Programme.institution)).where(Programme.institution_id == inst.id, Programme.branch_family == family)) if p.id in offered and not p.campus_city]
    if not rows:
        return None, 0
    rows.sort(key=lambda p: (p.duration_years != 4, len(p.name), p.id))
    return rows[0], len(rows) - 1


def _placement_line(records: list[dict]) -> dict | None:
    with_median = [r for r in records if r["median_salary_inr"]]
    if not with_median:
        return None
    best = sorted(with_median, key=lambda r: (r["scope"] != "programme", -r["graduation_year"]))[0]
    return _fact(f"Median salary {_inr(best['median_salary_inr'])}, graduating {best['graduation_year']} ({best['scope_label'].lower()}, self-reported).", best["source_title"], best["source_url"], best["graduation_year"], best["verification_status"])


def _academic_lines(name: str, profile: dict | None) -> tuple[list[dict], list[str]]:
    if not profile or not profile["source"]:
        facts = []
        if profile and profile["publications"]:
            pub = profile["publications"]
            facts.append(_fact(f"{name}: {pub['works_count']:,} indexed papers and {pub['cited_by_count']:,} citations. {pub['note']}", pub["source_title"], pub["source_url"], pub["retrieved"], pub["verification_status"]))
        return facts, [f"No NIRF faculty or research figures are on record for {name}."]
    source = profile["source"]
    cite = dict(title=source["title"], url=source["url"], year=source["submission_year"], status=source["verification_status"])
    teaching, experience, availability, research = profile["teaching"], profile["experience"], profile["availability"], profile["research"]
    facts = []
    if teaching["students_per_regular_faculty"]:
        facts.append(_fact(f"{name}, teaching: {teaching['students_total']:,} students and {teaching['faculty_regular']:,} regular faculty, or {teaching['students_per_regular_faculty']} students each. {teaching['note']}", **cite))
    if experience["phd_share"] is not None:
        facts.append(_fact(f"{name}, faculty experience: {round(experience['phd_share'] * 100)}% of regular faculty hold a doctorate, with a median of {experience['median_experience_years']} years' experience.", **cite))
    if availability["faculty_other_current"]:
        facts.append(_fact(f"{name}, faculty availability: {availability['faculty_other_current']:,} more people currently teach on visiting, adjunct or contract terms.", **cite))
    if research["years"]:
        latest = research["years"][0]
        facts.append(_fact(f"{name}, research in {latest['academic_year']}: {_inr(latest['sponsored_amount_inr'])} in sponsored funding, {latest['phd_graduated'] if latest['phd_graduated'] is not None else 'an unknown number of'} doctorates awarded and {latest['patents_granted'] if latest['patents_granted'] is not None else 'an unknown number of'} patents granted. {research['note']}", **cite))
    resources = profile["resources"]["years"]
    if resources and resources[0]["library_spend_inr"] is not None:
        facts.append(_fact(f"{name}, academic resources in {resources[0]['academic_year']}: {_inr(resources[0]['library_spend_inr'])} on the library and {_inr(resources[0]['equipment_spend_inr'])} on new equipment. {profile['resources']['note']}", **cite))
    if profile["publications"]:
        pub = profile["publications"]
        facts.append(_fact(f"{name}, publications: {pub['works_count']:,} indexed papers and {pub['cited_by_count']:,} citations. {pub['note']}", pub["source_title"], pub["source_url"], pub["retrieved"], pub["verification_status"]))
    gaps = [profile["scope_note"], "Named faculty profiles, department figures and student feedback on teaching aren't collected."]
    if source["issues"]:
        gaps.append(f"This submission has a problem and isn't compared with others: {source['issues']}.")
    return facts, gaps


def _reachable(db: Session, profile: StudentProfile | None) -> set[int] | None:
    """Institutes with an option in this student's shortlist, or None with no profile."""
    if profile is None:
        return None
    return {o["institution"]["slug"] for o in rec.generate(db, profile, per_band_limit=10 ** 6, record_run=False)["options"]}


def _scoped(profile: StudentProfile | None) -> str:
    return " Limited to institutes on your shortlist." if profile else " This covers all institutes with records. Add your rank to limit it to your shortlist."


def tool_process(question: str) -> dict | None:
    text = question.lower()
    for pattern, title, page, lines in PROCESS:
        if re.search(pattern, text):
            return _answer(
                "joint_seat_rules", f"{title}, from the JoSAA 2026 rules.", [_fact(line, f"{RULES_TITLE}, page {page} of the PDF", RULES_URL, 2026, "official") for line in lines],
                gaps=["These are the 2026 rules, summarised. Rules change each year, so check the current Business Rules before acting."],
            )
    return None


def tool_compare(db: Session, pairs: list[tuple[Institution, str | None]], profile: StudentProfile | None) -> dict:
    data_year = rec.latest_year(db)
    chosen, facts, gaps = [], [], []
    for inst, family in pairs[:4]:
        programme, others = _programme(db, inst, family, data_year)
        if programme is None:
            gaps.append(f"{inst.short_name}: name a branch it offers in {data_year} so I can compare a specific programme." if family is None else f"{inst.short_name} has no {FAMILY_LABELS.get(family, family)} programme in the {data_year} seat matrix.")
            continue
        chosen.append(programme.id)
        if others:
            gaps.append(f"{inst.short_name} has {others} other {FAMILY_LABELS.get(family, family)} programme{'s' if others > 1 else ''}. I used {programme.name}.")
    if len(chosen) < 2 and all(family is None for _, family in pairs):
        return tool_compare_institutes(db, [inst for inst, _ in pairs[:4]])
    if len(chosen) < 2:
        return _answer("compare_programmes", "I need two programmes to compare, each with an institute and a branch, such as NIT Trichy CSE or NIT Warangal ECE.", gaps=gaps)
    result = comparison.compare(db, chosen, profile)
    for item in result["items"]:
        name = f"{item['institution']['short_name']} {item['programme']}"
        cutoff = item["reference_cutoff"]
        if cutoff:
            facts.append(_fact(f"{name}: closed at {cutoff['closing_rank']:,} in {cutoff['year']} ({cutoff['quota']} quota, OPEN, gender-neutral). A past cutoff, not a chance of admission.", cutoff["source_title"], cutoff["source_url"], cutoff["year"], "official"))
        route = item.get("student_route")
        if route and route.get("band"):
            facts.append(_fact(f"{name}: for your rank, this is in the {route['band']} band, using past cutoffs ({route.get('explanation', '')})."))
        placement = _placement_line(item["placements"])
        if placement:
            placement["text"] = f"{name}: {placement['text']}"
            facts.append(placement)
        else:
            gaps.append(f"{name}: no placement median on record.")
        if item["ranking"]:
            r = item["ranking"]
            facts.append(_fact(f"{name}: NIRF {r['year']} Engineering rank {r['rank']} (secondary copy, whole institute).", r["source_name"], r["source_url"], r["year"], r["verification_status"]))
        if item["fee"]:
            f = item["fee"]
            cost = f"{_inr(f['annual_complete_inr'])} a year in total" if f["annual_complete_inr"] else f"at least {_inr(f['annual_known_inr'])} a year, with some charges missing"
            facts.append(_fact(f"{name}: fees {cost}, for {f['seat_type_group']}.", f["source_title"], f["source_url"], f["academic_year"], f["verification_status"]))
        else:
            gaps.append(f"{name}: no fee record.")
    return _answer(
        "compare_programmes", "Here's what the records show side by side. I won't pick one for you, because it depends on what you value.", facts, result["trade_offs"],
        gaps + ["Branch-specific placements are rarely published, so most figures here are institute-wide."],
    )


def tool_compare_institutes(db: Session, institutions: list[Institution]) -> dict:
    """No branch was named, so only whole-institute records can be set side by side."""
    evidence = rec.institution_evidence(db)
    facts, gaps = [], []
    for inst in institutions:
        ranking = evidence["rankings"].get(inst.id)
        if ranking:
            facts.append(_fact(f"{inst.short_name}: NIRF {ranking.year} Engineering rank {ranking.rank} (secondary copy).", ranking.source.name, ranking.source.url, ranking.year, ranking.verification_status))
        line = _placement_line(rec.placement_json([r for r in rec.latest_per_year(evidence["placements"].get(inst.id, [])) if r.scope == "institution"]))
        if line:
            line["text"] = f"{inst.short_name}: {line['text']}"
            facts.append(line)
        lines, missing = _academic_lines(inst.short_name, evidence["academics"].get(inst.id))
        facts += lines[:2]
        gaps += missing[:1] if not lines else []
    return _answer(
        "compare_institutes", "These are whole-institute records. Your branch can matter as much as the institute, so add one to each name for a closer comparison, such as IIT Bombay Civil or IIT Delhi CSE. I won't pick one for you.", facts,
        gaps=gaps + ["None of these figures is specific to a branch."],
    )


def tool_iit_vs_nit(db: Session, profile: StudentProfile | None) -> dict:
    reasoning = [
        "This is general reasoning, not a finding from our data. We hold too little branch-level evidence to settle it.",
        "An institute's name can open doors in recruiting and for further study. The branch shapes what you study each day and which jobs you're directly prepared for.",
        "If you want to work in the top branch's field, check whether the IIT's lower branch lets you get there, through branch change rules, minors or elective courses. Those vary, and we don't hold them.",
        "If you like the lower branch's subject for its own sake, the comparison is much easier.",
        "Ask both institutes for placement figures for the specific branch. Institute-wide figures can hide wide differences.",
    ]
    facts = []
    if profile:
        options = rec.generate(db, profile, per_band_limit=10 ** 6, record_run=False)["options"]
        iit = [o for o in options if o["institution"]["type"] == "IIT"][:2]
        nit = [o for o in options if o["institution"]["type"] == "NIT"][:2]
        for option in iit + nit:
            facts.append(_fact(f"On your shortlist: {option['institution']['short_name']} {option['programme']} ({option['band'] or 'limited history'}). Compare these by name for the details."))
    return _answer("iit_or_nit_reasoning", "There's no general answer. It depends on the two specific programmes and on what you want to do.", facts, reasoning, ["Branch change rules and curriculum aren't collected, and neither are career outcomes over time."], needs_profile=not profile)


def tool_consistency(db: Session, profile: StudentProfile | None) -> dict:
    evidence = rec.institution_evidence(db)
    reachable = _reachable(db, profile)
    rows = []
    for inst in db.scalars(select(Institution)):
        if reachable is not None and inst.slug not in reachable:
            continue
        records = [r for r in rec.latest_per_year(evidence["placements"].get(inst.id, [])) if r.reporting_definition == "nirf_graduation_outcomes" and r.scope == "institution" and r.median_salary_inr and r.graduating_students and r.graduating_students >= MIN_GRADUATING_CLASS]
        if len(records) < 3:
            continue
        rates = [100 * r.students_placed / r.graduating_students for r in records]
        medians = [r.median_salary_inr for r in records]
        latest = max(records, key=lambda r: r.graduation_year)
        rows.append({"inst": inst, "rate_range": max(rates) - min(rates), "rate_low": min(rates), "median_change": (max(medians) - min(medians)) / mean(medians), "latest": latest})
    rows = sorted([r for r in rows if r["rate_low"] >= 50], key=lambda r: (round(r["rate_range"] + 100 * r["median_change"]), r["inst"].short_name))[:LIMIT]
    facts = [
        _fact(f"{r['inst'].short_name}: share of graduating students placed moved by {r['rate_range']:.0f} percentage point{'' if round(r['rate_range']) == 1 else 's'} over 3 years, never below {r['rate_low']:.0f}%. Its median salary varied by {100 * r['median_change']:.0f}%. Latest median {_inr(r['latest'].median_salary_inr)}, graduating {r['latest'].graduation_year}.", r["latest"].source_document.title, r["latest"].source_document.url, r["latest"].graduation_year, r["latest"].verification_status)
        for r in rows
    ]
    return _answer(
        "placement_consistency", "These institutes changed least over 3 years in their NIRF figures. Steady doesn't mean high, so read the medians too." + _scoped(profile), facts,
        ["I measured this as the movement in placement rate plus the variation in median salary, and left out institutes that ever fell below 50% placed or graduate under 100 students. That formula is my choice, not a standard."],
        ["Figures are self-reported and institute-wide, not by branch. Institutes without three comparable years are left out, which isn't a sign of inconsistency."],
    )


def tool_value(db: Session, question: str, profile: StudentProfile | None) -> dict:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|l\b|crore|cr\b)", question.lower())
    if not match:
        return _answer("cost_within_budget", "Tell me a total budget, such as under ₹10 lakh for the whole degree.")
    budget = float(match[1]) * (10_000_000 if match[2].startswith("cr") else 100_000)
    evidence = rec.institution_evidence(db)
    reachable = _reachable(db, profile)
    complete, partial_over, partial_open = [], [], []
    for inst in db.scalars(select(Institution)):
        fee = evidence["fees"].get(inst.id)
        if fee is None or (reachable is not None and inst.slug not in reachable):
            continue
        yearly = rec.annual_cost(fee)
        if yearly is not None:
            total = yearly * 4 + (fee.one_time_inr or 0) - (fee.refundable_deposit_inr or 0)
            (complete if total <= budget else partial_over).append((inst, fee, total, True))
        else:
            known = rec.known_annual_charges(fee)
            if known is not None:
                total = known * 4 + (fee.one_time_inr or 0) - (fee.refundable_deposit_inr or 0)
                (partial_over if total > budget else partial_open).append((inst, fee, total, False))
    def line(inst, fee, total, whole):
        # No branch is named here, so one branch's median would misdescribe the institute.
        placed = rec.best_salary_record([r for r in rec.latest_per_year(evidence["placements"].get(inst.id, [])) if r.scope == "institution"])
        pay = f" Latest institute-wide median salary {_inr(placed.median_salary_inr)}, self-reported." if placed else " No institute-wide median on record."
        return _fact(f"{inst.short_name}: {'about' if whole else 'at least'} {_inr(total)} over 4 years{'' if whole else ', with hostel or mess charges missing'}, for {fee.seat_type_group}.{pay}", fee.source_document.title, fee.source_document.url, fee.academic_year, fee.verification_status)
    facts = [line(*row) for row in sorted(complete + partial_open, key=lambda r: r[2])]
    over = [line(*row) for row in sorted(partial_over, key=lambda r: r[2])[:4]]
    return _answer(
        "cost_within_budget", f"Fee records are too thin to name the best value under {_inr(budget)}. Here's every institute with a record that could fit." + _scoped(profile), facts + over,
        ["Totals assume this year's charges stay the same for 4 years, and leave out refundable deposits. Fees usually rise, and many institutes reduce or waive tuition by category and family income."],
        ["Only 12 of 139 institutes have a fee record, and 4 of those a complete yearly cost. An institute missing here may be cheaper or dearer."],
    )


def tool_higher_studies(db: Session, profile: StudentProfile | None) -> dict:
    evidence = rec.institution_evidence(db)
    reachable = _reachable(db, profile)
    rows = []
    for inst in db.scalars(select(Institution)):
        if reachable is not None and inst.slug not in reachable:
            continue
        records = [r for r in rec.latest_per_year(evidence["placements"].get(inst.id, [])) if r.reporting_definition == "nirf_graduation_outcomes" and r.higher_studies_students is not None and r.graduating_students and r.graduating_students >= MIN_GRADUATING_CLASS]
        if records:
            latest = max(records, key=lambda r: r.graduation_year)
            rows.append((latest.higher_studies_students / latest.graduating_students, inst, latest))
    rows.sort(key=lambda r: (-r[0], r[1].short_name))
    facts = []
    for share, inst, record in rows[:LIMIT]:
        profile_academic = evidence["academics"].get(inst.id)
        research = (profile_academic or {}).get("scores", {}).get("research")
        extra = f" Funded research and doctorates per faculty member are above about {round(research)}% of comparable institutes." if research is not None else ""
        facts.append(_fact(f"{inst.short_name}: {100 * share:.0f}% of 4-year graduates went on to higher studies, graduating {record.graduation_year}.{extra}", record.source_document.title, record.source_document.url, record.graduation_year, record.verification_status))
    return _answer(
        "higher_studies", "These institutes report the largest share of graduates going on to further study." + _scoped(profile), facts,
        ["To see how this changes your shortlist, choose research as a career goal and raise the research slider. It re-orders the options but never changes your admission bands."],
        ["Self-reported and institute-wide. Where graduates study, and in what subject, isn't recorded."],
    )


def tool_flexibility() -> dict:
    return _answer(
        "branch_flexibility", "We hold no measured data on career flexibility by branch, so this is general reasoning.",
        reasoning=[f"{FAMILY_LABELS[family]}: {note}." for family, note in comparison.BROAD_CAREER_NOTES.items() if family in ("CS", "MATH_COMP", "ECE", "EE", "ME", "CIVIL", "CHEM_E")] + ["These are broad product assumptions, not outcomes we've measured, and they vary by institute."],
        gaps=["Branch change rules, minors and curriculum aren't collected. Ask each institute about them."],
    )


def tool_institution(db: Session, inst: Institution, question: str, family: str | None, profile: StudentProfile | None) -> dict:
    text = question.lower()
    evidence = rec.institution_evidence(db)
    data_year = rec.latest_year(db)
    name = inst.short_name
    wants_faculty = re.search(r"facult|research|professor|teacher|teaching|academic|phd|doctora|patent|paper|publication", text)
    wants_fee = re.search(r"\bfee|cost|tuition|hostel|mess\b", text)
    wants_cutoff = re.search(r"cutoff|cut off|closing|chance|can i get|rank|admission", text)
    wants_placement = re.search(r"placement|package|salary|ctc|job|recruit", text)
    facts, gaps = [], []
    if wants_faculty or not (wants_fee or wants_cutoff or wants_placement):
        lines, missing = _academic_lines(name, evidence["academics"].get(inst.id))
        facts += lines
        gaps += missing
    if wants_fee or not (wants_faculty or wants_cutoff or wants_placement):
        fee = evidence["fees"].get(inst.id)
        if fee:
            yearly = rec.annual_cost(fee)
            cost = f"{_inr(yearly)} a year in total" if yearly else f"at least {_inr(rec.known_annual_charges(fee))} a year, with some charges missing" if rec.known_annual_charges(fee) else f"{_inr(fee.payable_at_admission_inr)} at first payment"
            facts.append(_fact(f"{name} fees: {cost}, for {fee.seat_type_group}. {fee.notes or ''}".strip(), fee.source_document.title, fee.source_document.url, fee.academic_year, fee.verification_status))
        else:
            gaps.append(f"No fee record for {name}. Please check the institute's website.")
    if wants_placement or not (wants_faculty or wants_fee or wants_cutoff):
        records = rec.latest_per_year(evidence["placements"].get(inst.id, []))
        line = _placement_line(rec.placement_json(records))
        if line:
            line["text"] = f"{name}: {line['text']}"
            facts.append(line)
        else:
            gaps.append(f"No placement median on record for {name}.")
    if wants_cutoff:
        programme, others = _programme(db, inst, family, data_year)
        if programme is None:
            gaps.append(f"Name a branch at {name} to see its closing ranks, such as {name} CSE.")
        else:
            ids = rec.history_ids(rec.lineage_map(db), programme.id)
            rows = db.scalars(select(CutoffRecord).options(joinedload(CutoffRecord.source_document)).where(CutoffRecord.programme_id.in_(ids), CutoffRecord.is_final_round, CutoffRecord.seat_type == "OPEN", CutoffRecord.gender_pool == "neutral", CutoffRecord.quota.in_(("AI", "OS")), CutoffRecord.closing_rank.is_not(None), CutoffRecord.is_preparatory.is_(False)).order_by(CutoffRecord.year.desc())).all()
            for row in rows[:4]:
                facts.append(_fact(f"{name} {programme.name}: closed at {row.closing_rank:,} in {row.year} ({row.quota} quota, OPEN, gender-neutral, final round).", row.source_document.title, row.source_document.url, row.year, "official"))
            route = comparison.compare(db, [programme.id], profile)["items"][0]["student_route"] if profile else None
            if route:
                facts.insert(0, _fact(f"For your rank, {name} {programme.name} is in the {route['band'] or 'limited history'} band, using past cutoffs. {route['explanation']}"))
            elif profile:
                gaps.append(f"No seat at {name} {programme.name} applies to your category and rank list.")
            else:
                gaps.append("These are past cutoffs for one seat type. Add your rank and category for the band that applies to you.")
            gaps.append("Past cutoffs aren't a chance of admission, and we don't give a percentage.")
    if re.search(r"best (professor|teacher|faculty)|good (professor|teacher)|rate .*(professor|teacher)", text):
        return _answer("institute_records", f"I don't rate or rank individual teachers, and we hold no student feedback on teaching. Here's what's on record for {inst.official_name} as a whole.", facts, gaps=gaps)
    if re.search(r"\b(good|bad|best|worth|better|should i)\b", text):
        return _answer("institute_records", f"I can't tell you whether {name} is good, because that depends on what you want. Here's what's on record for {inst.official_name}.", facts, gaps=gaps)
    return _answer("institute_records", f"Records on file for {inst.official_name}.", facts, gaps=gaps)


def tool_shortlist(db: Session, profile: StudentProfile | None) -> dict:
    if profile is None:
        return _answer("student_shortlist", "I need your rank and category for that. Fill in your details, then ask again or open your shortlist.", needs_profile=True)
    result = rec.generate(db, profile, per_band_limit=3, record_run=False)
    facts = [_fact(f"{o['institution']['short_name']} {o['programme']}: {o['band'] or 'limited history'} band. {o['best_route']['explanation']}") for o in result["options"][:LIMIT]]
    return _answer("student_shortlist", f"The top of your shortlist, with {sum(result['counts'].values())} options in all. Open your shortlist to adjust your priorities.", facts, gaps=result["warnings"][:1])


def answer(db: Session, question: str, profile: StudentProfile | None = None) -> dict:
    text = question.lower()
    process = tool_process(text)
    institutions = find_institutions(db, question)
    if process and len(institutions) == 0:
        return process
    if re.search(r"\biit\b.*\b(lower|low|core)\b.*\bnit\b|\bnit\b.*\b(top|higher|cse|cs)\b.*\biit\b|iit.*(or|vs|versus|better).*nit", text) and not institutions:
        return tool_iit_vs_nit(db, profile)
    if len(institutions) >= 2:
        return tool_compare(db, _pairs(db, question, institutions), profile)
    if re.search(r"consisten|stable|steady", text):
        return tool_consistency(db, profile)
    if re.search(r"higher stud|further stud|masters|\bms\b|\bphd\b.*(after|instead)|instead of placement", text) and not institutions:
        return tool_higher_studies(db, profile)
    if re.search(r"flexib|switch.*(career|field)|versatile", text) and not institutions:
        return tool_flexibility()
    if re.search(r"value|under|within|budget|cheap|afford|less than", text) and re.search(r"lakh|lac|crore|\bl\b|\bcr\b", text) and not institutions:
        return tool_value(db, question, profile)
    if institutions:
        pair = _pairs(db, question, institutions)[0]
        result = tool_institution(db, pair[0], question, pair[1], profile)
        if re.search(r"\b(or|vs|versus|compared? (to|with))\b", text):
            result["summary"] = f"I only recognised {pair[0].short_name} here, so this isn't a comparison. The other option may not be in JoSAA's list, which is all I hold. {result['summary']}"
        return result
    if re.search(r"my (options|shortlist|chances)|what can i get|which college|where can i|best (college|option)s? for me", text):
        return tool_shortlist(db, profile)
    return _answer("not_understood", "I can't answer that from the records I hold. I can only use stored data, so try one of these, or name an institute and a branch.")
