"""Attach the fees deemed universities declared to MCC to the NEET UG route, word for word.

MCC publishes each participating institute's own "Proforma for college: information regarding fee, bond and
conditions" (Annexure C) on its public Participating Institute Details page. The college fills it in, so figures
are shown exactly as written, labelled as declared by the college, with a link to the document. A field the
college left as 0 or blank shows nothing, so the page says the fee isn't available rather than guessing.

Inputs (git-ignored): data/raw/mcc/profiles/<MCC institute code>.pdf, saved from
https://mcc.admissions.nic.in/Applicant/Handler/ViewInstituteProfileDetailsDynamic.ashx?boardId=140032621&InstituteId=<code>,
and data/raw/mcc/profiles/institutes.json, MCC's list of deemed institute codes and names.

Usage: python -m ingest.mcc_fees
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "raw" / "mcc" / "profiles"
ROUTES = ROOT / "backend" / "snapshot" / "exam_routes.json"
PROFILE_URL = "https://mcc.admissions.nic.in/Applicant/Handler/ViewInstituteProfileDetailsDynamic.ashx?boardId=140032621&InstituteId={code}"

# The proforma's fields, in its own order. Each label runs until its colon; its value runs until the next label.
LABEL_STARTS = (
    "Name of the College", "Complete Mailing Address", "State:", "Pin Code", "Name of Affiliating University",
    "Amount to be Paid", "Amount to be paid", "Stipend Paid", "Hostel facility", "The Amount of", "Annual Fees",
    "Website Address", "Other Info", "Miscellaneous Charges", "PwBD Friendly", "Contact Details",
)
# Fields shown to students, with the label we show. NRI amounts in dollars and refund rules are left in the document.
SHOWN = [
    (re.compile(r"^Annual Fees of Candidates\(INR\)"), "Annual fee"),
    (re.compile(r"^Amount to be Paid at the time of Admission \(including Hostel fees\) \(INR\)"), "Payable at admission, including hostel"),
    *[(re.compile(rf"^Amount to be paid at the time of Admission\(Including Hostel Fee\s*{n}\s*Year\)\s*in INR"), f"Year {i}, including hostel")
      for i, n in enumerate(["1st", "2nd", "3rd", "4th", "5th"], start=1)],
]


def fields(text: str) -> dict[str, str]:
    """Label and value pairs from a proforma's text, with whitespace collapsed."""
    out: dict[str, str] = {}
    label: list[str] = []
    value: list[str] = []
    reading_label = False
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if line.startswith(LABEL_STARTS) or (reading_label and not label[-1].endswith(":")):
            if label and not reading_label:
                out[" ".join(label)] = " ".join(value)
            if not reading_label:
                label, value = [], []
            label.append(line)
            reading_label = not line.endswith(":")
            continue
        if reading_label:
            label.append(line)
            reading_label = not line.endswith(":")
            continue
        value.append(line)
    if label:
        out[" ".join(label)] = " ".join(value)
    return {re.sub(r"\s+", " ", k).rstrip(" :"): re.sub(r"\s+", " ", v).strip() for k, v in out.items()}


def declared(path: Path) -> list[dict]:
    """The fee fields a college filled in, word for word, in the proforma's order."""
    text = "\n".join(page.get_text() for page in pymupdf.open(path))
    found = []
    for label, value in fields(text).items():
        for pattern, shown in SHOWN:
            if pattern.match(label) and value and value not in ("0", "0.00", "NA", "N/A", "-"):
                found.append({"label": shown, "value": value})
    return found


def key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match(mcc_name: str, institutes: set[str]) -> str | None:
    """The NEET record institute that starts with MCC's institute name, if exactly one does."""
    wanted = key(mcc_name)
    hits = [i for i in institutes if key(i).startswith(wanted)]
    return hits[0] if len(hits) == 1 else None


def attach(data: dict, listing: dict, retrieved: str) -> dict[str, int]:
    route = next(r for r in data["routes"] if r["code"] == "neet-ug")
    institutes = {r["institute"] for r in route["records"]}
    fees: dict[str, dict] = {}
    report = {"listed": 0, "profile": 0, "with_fee": 0, "matched": 0}
    unmatched = []
    for code, name in listing["institutes"]:
        report["listed"] += 1
        path = PROFILES / f"{code}.pdf"
        if not path.exists() or path.stat().st_size == 0:
            continue
        report["profile"] += 1
        found = declared(path)
        if not found:
            continue
        report["with_fee"] += 1
        institute = match(name, institutes)
        if institute is None:
            unmatched.append(name)
            continue
        report["matched"] += 1
        fees[institute] = {
            "title": "Fees as declared by the college to MCC",
            "note": "Copied word for word from the college's own form on MCC. We haven't checked these figures, and colleges fill the fields in differently. Confirm with the college before paying.",
            "declared": found, "source_url": PROFILE_URL.format(code=code), "mcc_code": code,
            "status": "declared by the college", "year": "2026", "retrieved": retrieved,
        }
    for record in route["records"]:
        record.pop("fee", None)
        if record["institute"] in fees:
            record["fee"] = fees[record["institute"]]
    if unmatched:
        print("No single NEET institute matches:", unmatched)
    return report


if __name__ == "__main__":
    listing = json.loads((PROFILES / "institutes.json").read_text())
    data = json.loads(ROUTES.read_text())
    print(attach(data, listing, listing["retrieved"]))
    ROUTES.write_text(json.dumps(data))
