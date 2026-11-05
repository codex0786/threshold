"""Education cost and loan illustration. Pure functions, and estimates rather than forecasts."""
from __future__ import annotations

from dataclasses import dataclass

LOW_FACTOR = 0.70
HIGH_FACTOR = 1.30
DEFAULT_TAKE_HOME = 0.70
DEFAULT_REPAYMENT_SHARE = 0.40


@dataclass(frozen=True)
class CostInputs:
    annual_tuition: int
    annual_hostel: int
    annual_mess: int
    annual_other: int
    one_time: int
    refundable_deposit: int
    annual_living: int
    annual_scholarship: int
    years: int


def total_cost(c: CostInputs) -> dict:
    annual = c.annual_tuition + c.annual_hostel + c.annual_mess + c.annual_other + c.annual_living
    net_annual = max(0, annual - c.annual_scholarship)
    total = net_annual * c.years + c.one_time + c.refundable_deposit
    return {"annual_cost": annual, "annual_after_scholarship": net_annual, "total_cost": total, "total_excluding_refundable": total - c.refundable_deposit}


def emi(principal: float, annual_rate_percent: float, years: int) -> float:
    if principal <= 0:
        return 0.0
    months = years * 12
    if annual_rate_percent == 0:
        return principal / months
    r = annual_rate_percent / 1200
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def loan(amount: int, annual_rate_percent: float, repayment_years: int, moratorium_months: int) -> dict:
    """Interest during study and any grace period accrues as simple interest and is added to the balance.

    Lenders differ on this, so the figures are illustrative.
    """
    accrued = amount * annual_rate_percent / 100 * moratorium_months / 12
    balance = amount + accrued
    monthly = emi(balance, annual_rate_percent, repayment_years)
    total_paid = monthly * repayment_years * 12
    return {
        "loan_amount": amount, "interest_during_moratorium": round(accrued), "balance_at_repayment": round(balance), "monthly_emi": round(monthly),
        "total_repaid": round(total_paid), "total_interest": round(total_paid - amount),
    }


def scenario(name: str, annual_ctc: int, take_home_share: float, repayment_share: float, monthly_emi: float, payback_amount: float) -> dict:
    monthly_take_home = annual_ctc * take_home_share / 12
    set_aside = monthly_take_home * repayment_share
    share = monthly_emi / monthly_take_home if monthly_take_home else None
    return {
        "name": name, "annual_ctc": annual_ctc, "monthly_take_home": round(monthly_take_home),
        "emi_share_of_take_home": round(100 * share, 1) if share is not None else None,
        "illustrative_payback_years": round(payback_amount / (set_aside * 12), 1) if set_aside > 0 else None,
        "emi_warning": bool(share is not None and share > repayment_share),
    }


def salary_scenarios(median_ctc: int | None, low: int | None, high: int | None) -> dict[str, int] | None:
    """Low and high default to fixed shares of the median. They are assumptions, not reported figures."""
    if median_ctc is None:
        return None
    return {"Low": low if low is not None else round(median_ctc * LOW_FACTOR), "Base": median_ctc, "High": high if high is not None else round(median_ctc * HIGH_FACTOR)}
