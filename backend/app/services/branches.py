"""Group raw programme names into branch families. Order matters: specific rules come first."""
from __future__ import annotations

import re

_RULES: list[tuple[str, str]] = [
    (r"naval architecture|ocean engineering", "OCEAN"),
    (r"\barchitecture\b", "ARCH"),
    (r"\bplanning\b", "PLANNING"),
    (r"artificial intelligence|machine learning|data science|data analytics|\bai\b", "AI_DS"),
    (r"computer|information technology|software|cyber|computing|\(it\)|\(cse\)|internet of things|intelligent systems", "CS"),
    (r"electrical|elctrical|power", "EE"),
    (r"electronics|electronic |communication|vlsi|integrated circuit|instrumentation|semiconductor", "ECE"),
    (r"mechatronics|robotics|automation", "ROBOTICS"),
    (r"aerospace|aeronautical", "AERO"),
    (r"mechanical|production|industrial|manufacturing|automobile|\(me\)", "ME"),
    (r"civil|infrastructure|construction|in ce\.", "CIVIL"),
    (r"chemical|petroleum|polymer|ceramic", "CHEM_E"),
    (r"bio|food|pharma|agricultural", "BIO"),
    (r"metallurg|material|mining|mineral", "MATERIALS"),
    (r"physics|chemistry|mathematics|economics|statistics|science", "SCIENCE"),
]
_COMPILED = [(re.compile(p, re.I), family) for p, family in _RULES]

FAMILY_LABELS = {
    "CS": "Computer Science & IT", "AI_DS": "AI & Data Science", "MATH_COMP": "Mathematics & Computing",
    "ECE": "Electronics & Communication", "EE": "Electrical", "ROBOTICS": "Robotics & Mechatronics",
    "ME": "Mechanical & Production", "AERO": "Aerospace", "CIVIL": "Civil & Infrastructure",
    "CHEM_E": "Chemical & Process", "BIO": "Biotechnology & Food", "MATERIALS": "Materials, Metallurgy & Mining",
    "OCEAN": "Ocean & Naval", "SCIENCE": "Sciences & Economics", "ARCH": "Architecture",
    "PLANNING": "Planning", "OTHER": "Other",
}

# Product assumption, not evidence: which branches commonly lead towards each career goal.
# Shown to the student as an assumption and adjustable through their own branch preferences.
CAREER_BRANCH_AFFINITY: dict[str, set[str]] = {
    "software": {"CS", "AI_DS", "MATH_COMP"},
    "ai_ml": {"AI_DS", "CS", "MATH_COMP"},
    "core": {"ME", "CIVIL", "CHEM_E", "EE", "AERO", "MATERIALS", "OCEAN", "ROBOTICS"},
    "electronics": {"ECE", "EE"},
    "research": {"SCIENCE", "MATH_COMP", "BIO"},
}


def branch_family(programme_name: str) -> str:
    name = re.sub(r"\s+", " ", programme_name)
    # Maths and computing names mention "computing", so they are checked before the CS rule.
    if re.search(r"mathematics", name, re.I) and re.search(r"comput|data", name, re.I):
        return "MATH_COMP"
    for pattern, family in _COMPILED:
        if pattern.search(name):
            return family
    return "OTHER"


def required_paper(institute_type: str, degree: str | None, programme_name: str) -> str:
    """Which exam paper's rank list applies (Business Rules clause 2)."""
    if institute_type in ("IIT", "IISC"):
        return "advanced"
    degree_text = (degree or "").lower()
    if "architecture" in degree_text:
        return "main_paper2a"
    if "planning" in degree_text:
        return "main_paper2b"
    return "main_paper1"
