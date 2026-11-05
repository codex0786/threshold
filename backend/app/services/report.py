"""Assemble a plain-language decision report for parents from stored records."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Programme
from app.schemas import StudentProfile
from app.services import careers, finance, preferences
from app.services import recommend as rec

BRANCH_PLAIN = {
    "CS": "Designing and building software and computer systems.",
    "AI_DS": "Working with data and building systems that learn from it.",
    "MATH_COMP": "Mathematics applied to computing, data and finance.",
    "ECE": "Electronic devices, chips and communication systems such as mobile networks.",
    "EE": "Power generation, electrical machines and electronic control.",
    "ROBOTICS": "Machines that combine mechanical parts, electronics and software.",
    "ME": "Designing and manufacturing machines, engines and products.",
    "AERO": "Aircraft, spacecraft and related systems.",
    "CIVIL": "Buildings, roads, bridges, water and other infrastructure.",
    "CHEM_E": "Large-scale production of chemicals, fuels and materials.",
    "BIO": "Applying biology to medicine, food and industry.",
    "MATERIALS": "Metals, mining and engineering materials.",
    "OCEAN": "Ships and offshore structures.",
    "SCIENCE": "Science and mathematics, often leading to further study or research.",
}
BAND_PLAIN = {
    "safer": ("Likely within reach, based on the past", "The student's rank has been comfortably inside this seat's closing rank in recent years. It's still not guaranteed."),
    "competitive": ("Could go either way", "The student's rank is close to recent closing ranks."),
    "ambitious": ("A stretch", "The student's rank is outside recent closing ranks. It would need cutoffs to move favourably."),
    "beyond": ("Unlikely, based on the past", "The student's rank is well outside recent closing ranks."),
    None: ("Not enough history", "There are too few recent years of matching data to say."),
}
GLOSSARY = [
    ("JoSAA", "The body that allots seats at IITs, NITs, IIITs and other government-funded institutes."),
    ("Closing rank", "The rank of the last student given a seat. It changes every year."),
    ("Median salary", "The middle salary among placed students: half earned more and half earned less. It's a better guide than the highest package."),
    ("CTC", "Cost to company. It includes items beyond take-home pay, so monthly pay in hand is usually much lower."),
    ("Institute-wide", "Covers all students of a course level at the institute. Individual branches can be much higher or lower."),
]


def _risks(item: dict, option: dict) -> list[str]:
    risks = []
    if item.get("band") in ("ambitious", "beyond", None):
        risks.append(BAND_PLAIN[item.get("band")][1])
    if not any(p["scope"] == "programme" for p in option["placements"]):
        risks.append("No figures specific to this branch are on record, so its job outcomes could differ a lot from the institute's.")
    if option["fee"] is None:
        risks.append("No verified fee information is on record. Ask the institute for the full cost.")
    elif option["fee"]["annual_complete_inr"] is None:
        risks.append("Published fee information is partial, so the true yearly cost will be higher than the figures shown here.")
    return risks


def build(db: Session, profile: StudentProfile, programme_ids: list[int]) -> dict | None:
    programmes = {p.id: p for p in db.scalars(select(Programme).where(Programme.id.in_(programme_ids)).options(joinedload(Programme.institution)))}
    if len(programmes) != len(set(programme_ids)):
        return None
    evidence = rec.institution_evidence(db)
    analysis = preferences.analyse(db, profile, programme_ids)
    options = []
    for item in analysis["items"]:
        programme = programmes[item["programme_id"]]
        inst = programme.institution
        records, _ = rec.career_for(programme, evidence)
        placement = rec.placement_json(records)
        fee = rec.fee_json(evidence["fees"].get(inst.id))
        ranking = rec.ranking_json(evidence["rankings"].get(inst.id))
        own = next((p for p in placement if p["scope"] == "programme" and p["median_salary_inr"]), None)
        nirf = next((p for p in placement if p["reporting_definition"].startswith("nirf_") and p["median_salary_inr"]), None)
        salary = own or nirf
        loan = None
        known_annual = None
        if fee and fee["annual_tuition_inr"] is not None:
            known_annual = sum(fee[k] or 0 for k in ("annual_tuition_inr", "annual_hostel_inr", "annual_mess_inr", "annual_other_inr"))
            years = programme.duration_years or 4
            known_total = known_annual * years + (fee["one_time_inr"] or 0) + (fee["refundable_deposit_inr"] or 0)
            terms = finance.loan(known_total, 9.0, 10, years * 12 + 12)
            scenarios = []
            if salary:
                for name, ctc in (finance.salary_scenarios(salary["median_salary_inr"], None, None) or {}).items():
                    scenarios.append(finance.scenario(name, ctc, finance.DEFAULT_TAKE_HOME, finance.DEFAULT_REPAYMENT_SHARE, terms["monthly_emi"], terms["total_repaid"]))
            loan = {"known_total": known_total, "complete": fee["annual_complete_inr"] is not None, "terms": terms, "scenarios": scenarios}
        option = {"placements": placement, "fee": fee}
        band_title, band_text = BAND_PLAIN.get(item.get("band"), BAND_PLAIN[None])
        options.append({
            "position": item["position"], "programme_id": programme.id, "programme": programme.name, "degree": programme.degree, "duration_years": programme.duration_years,
            "branch_plain": BRANCH_PLAIN.get(programme.branch_family, "See the institute's website for what this programme covers."),
            "institution": {"short_name": inst.short_name, "official_name": inst.official_name, "type": inst.institute_type, "city": inst.city, "state": inst.state},
            "admission": {
                "title": band_title, "text": band_text, "band": item.get("band"), "issues": item["issues"],
                "routes": [{**route, "explanation": route["explanation"].replace("Your rank", "The student's rank")} for route in item.get("routes", [])[:1]],
            },
            "ranking": ranking, "placement_highlight": salary, "placements": placement, "fee": fee, "known_annual": known_annual, "loan": loan,
            "careers": careers.career_profile(db, inst.id), "risks": _risks(item, option),
        })
    return {
        "generated_on": date.today().isoformat(), "data_year": analysis["data_year"],
        "student": {
            "category": profile.category, "state": profile.eligibility_state, "is_pwd": profile.is_pwd,
            "main_rank": profile.main.crl, "main_category_rank": profile.main.category_rank, "advanced_rank": profile.advanced.crl,
            "goals": profile.career_goals, "preferred_branches": profile.preferred_branches,
        },
        "options": options, "advice": analysis["advice"], "glossary": GLOSSARY, "rules": analysis["rules"],
        "limits": [
            "This report is a decision aid. It doesn't guarantee admission, a job or a salary.",
            "It covers JoSAA only, not CSAB special rounds, state counselling or private colleges.",
            "Placement figures are reported by institutes themselves and haven't been audited.",
            "Loan figures assume 9% interest over 10 years, with interest added during study and one further year. Your lender's terms will differ.",
            "Low and high salary scenarios are 70% and 130% of the reported median. They are assumptions, not reported figures.",
            "Always confirm details on the official JoSAA website and with each institute.",
        ],
    }
