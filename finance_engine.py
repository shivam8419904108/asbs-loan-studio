from dataclasses import dataclass
from datetime import date, datetime
from calendar import monthrange
import math

ANNUAL_BASIS = 365
REGULAR_DAYS = 30
MONEY_TOLERANCE = 1.0

@dataclass(frozen=True)
class ROIChange:
    effective_date: date
    annual_rate: float
    note: str = ""

@dataclass(frozen=True)
class Prepayment:
    event_date: date
    amount: float
    effect: str
    note: str = ""

@dataclass
class ScheduleRow:
    emi_no: int
    due_date: date
    opening_principal: float
    roi: float
    interest_component: float
    principal_component: float
    emi: float
    part_prepayment: float
    closing_principal: float


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def add_months(day, months):
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def rupee(value):
    """Round to nearest whole rupee and store as float for x.00 display."""
    return float(round(float(value)))


def periodic_rate(annual_rate):
    return float(annual_rate) * REGULAR_DAYS / ANNUAL_BASIS


def raw_emi(principal, tenure, annual_rate):
    principal = float(principal)
    tenure = int(tenure)
    if principal <= 0 or tenure <= 0:
        raise ValueError("Principal and tenure must be greater than zero.")
    rate = periodic_rate(annual_rate)
    if abs(rate) < 1e-15:
        return principal / tenure
    return principal * rate / (1 - (1 + rate) ** (-tenure))


def emi_amount(principal, tenure, annual_rate):
    return rupee(raw_emi(principal, tenure, annual_rate))


def principal_from_emi(emi, tenure, annual_rate):
    emi = float(emi)
    tenure = int(tenure)
    if emi <= 0 or tenure <= 0:
        raise ValueError("EMI and tenure must be greater than zero.")
    rate = periodic_rate(annual_rate)
    value = emi * tenure if abs(rate) < 1e-15 else emi * (1 - (1 + rate) ** (-tenure)) / rate
    return rupee(value)


def tenure_from_emi(principal, emi, annual_rate):
    principal, emi = float(principal), float(emi)
    if principal <= 0 or emi <= 0:
        raise ValueError("Principal and EMI must be greater than zero.")
    rate = periodic_rate(annual_rate)
    if abs(rate) < 1e-15:
        return math.ceil(principal / emi)
    if emi <= principal * rate:
        raise ValueError("EMI is insufficient to cover periodic interest.")
    return math.ceil(-math.log(1 - principal * rate / emi) / math.log(1 + rate))


def roi_from_emi(principal, tenure, emi):
    """Solve annual ROI without an artificial 100% cap."""
    principal, emi, tenure = float(principal), float(emi), int(tenure)
    if principal <= 0 or tenure <= 0 or emi <= 0:
        raise ValueError("Principal, tenure and EMI must be greater than zero.")
    if emi < principal / tenure:
        raise ValueError("EMI is below the zero-interest EMI. Verify the inputs.")

    low, high = 0.0, 1.0
    while raw_emi(principal, tenure, high) < emi:
        high *= 2
        if high > 10.0:
            raise ValueError("Calculated ROI exceeds 1,000% p.a. Verify the inputs.")

    for _ in range(250):
        middle = (low + high) / 2
        if raw_emi(principal, tenure, middle) < emi:
            low = middle
        else:
            high = middle
    annual_rate = (low + high) / 2
    if abs(raw_emi(principal, tenure, annual_rate) - emi) > 0.01:
        raise ValueError("ROI calculation did not reconcile with the EMI.")
    return annual_rate


def solve_missing(target, principal, tenure, roi_pct, emi):
    warning = ""
    annual_rate = float(roi_pct) / 100
    if target == "EMI":
        emi = emi_amount(principal, tenure, annual_rate)
    elif target == "Principal":
        principal = principal_from_emi(emi, tenure, annual_rate)
    elif target == "Tenure":
        tenure = tenure_from_emi(principal, emi, annual_rate)
    elif target == "ROI":
        annual_rate = roi_from_emi(principal, tenure, emi)
        roi_pct = annual_rate * 100
        if roi_pct > 100:
            warning = "Calculated ROI is above 100% p.a. Please verify Principal, Tenure and EMI."
    else:
        raise ValueError("Unknown calculation target.")

    reverse_raw = raw_emi(principal, int(tenure), annual_rate)
    variance = reverse_raw - float(emi)
    return {
        "principal": rupee(principal),
        "tenure": int(tenure),
        "roi_pct": float(roi_pct),
        "emi": rupee(emi),
        "variance": variance,
        "warning": warning,
        "control": "PASS" if abs(variance) <= 1.0 else "REVIEW",
    }


def rate_on(day, initial_rate, changes):
    rate = float(initial_rate)
    for change in sorted(changes, key=lambda item: item.effective_date):
        if change.effective_date <= day:
            rate = change.annual_rate
        else:
            break
    return rate


def calculate_period_interest(opening, start, end, initial_rate, changes, available_payments):
    events = []
    for change in changes:
        if start < change.effective_date < end:
            events.append((change.effective_date, 0, "rate", change))
    for index, payment in available_payments:
        if start <= payment.event_date < end:
            events.append((payment.event_date, 1, "payment", (index, payment)))
    events.sort(key=lambda event: (event[0], event[1]))

    cursor = start
    rate = rate_on(start, initial_rate, changes)
    balance = float(opening)
    interest = 0.0
    applied = []
    for event_day, _, event_type, event in events:
        interest += balance * rate * (event_day - cursor).days / ANNUAL_BASIS
        cursor = event_day
        if event_type == "rate":
            rate = event.annual_rate
        else:
            index, payment = event
            amount = min(balance, rupee(payment.amount))
            balance -= amount
            applied.append((index, amount, payment.effect))
    interest += balance * rate * (end - cursor).days / ANNUAL_BASIS
    return rupee(max(0, interest)), applied


def generate_schedule(principal, disbursement, first_emi, tenure, initial_rate,
                      changes=(), prepayments=(),
                      roi_treatment="Recalculate EMI / Keep Tenure"):
    principal = rupee(principal)
    disbursement, first_emi = as_date(disbursement), as_date(first_emi)
    tenure = int(tenure)
    initial_rate = float(initial_rate)
    if principal <= 0 or tenure <= 0:
        raise ValueError("Principal and tenure must be greater than zero.")
    if first_emi < disbursement:
        raise ValueError("First EMI date cannot be before disbursement date.")
    if not 0 <= initial_rate <= 10:
        raise ValueError("Initial ROI must be between 0% and 1,000% p.a.")

    changes = sorted(
        [ROIChange(as_date(c.effective_date), float(c.annual_rate), c.note) for c in changes],
        key=lambda item: item.effective_date,
    )
    payments = sorted(
        [Prepayment(as_date(p.event_date), rupee(p.amount), p.effect, p.note) for p in prepayments],
        key=lambda item: item.event_date,
    )
    if any(c.annual_rate < 0 or c.annual_rate > 10 for c in changes):
        raise ValueError("ROI change must be between 0% and 1,000% p.a.")
    if any(p.amount <= 0 for p in payments):
        raise ValueError("Part-payment amount must be greater than zero.")

    balance = principal
    remaining = tenure
    original_emi = emi_amount(balance, tenure, initial_rate)
    current_emi = original_emi
    previous_due = add_months(first_emi, -1)
    last_due_rate = rate_on(first_emi, initial_rate, changes)
    used_payments = set()
    rows = []

    for emi_no in range(1, tenure + 1):
        if balance <= MONEY_TOLERANCE:
            break
        due_date = add_months(first_emi, emi_no - 1)
        opening = rupee(balance)
        due_rate = rate_on(due_date, initial_rate, changes)
        if roi_treatment == "Recalculate EMI / Keep Tenure" and abs(due_rate - last_due_rate) > 1e-15:
            current_emi = emi_amount(opening, max(1, remaining), due_rate)

        available = [(i, p) for i, p in enumerate(payments) if i not in used_payments]
        interest, applied = calculate_period_interest(
            opening, previous_due, due_date, initial_rate, changes, available
        )
        prepayment_total = 0.0
        reduce_emi = False
        for index, amount, effect in applied:
            used_payments.add(index)
            prepayment_total += amount
            reduce_emi = reduce_emi or effect == "Reduce EMI"
        prepayment_total = rupee(prepayment_total)
        available_principal = rupee(max(0, opening - prepayment_total))

        if emi_no == tenure:
            principal_component = available_principal
            cash_emi = rupee(interest + principal_component)
            closing = 0.0
        else:
            principal_component = rupee(max(0, min(available_principal, current_emi - interest)))
            closing = rupee(max(0, available_principal - principal_component))
            cash_emi = rupee(interest + principal_component) if closing <= MONEY_TOLERANCE else current_emi
            if closing <= MONEY_TOLERANCE:
                closing = 0.0

        rows.append(ScheduleRow(
            emi_no, due_date, opening, due_rate, interest, principal_component,
            cash_emi, prepayment_total, closing,
        ))
        balance = closing
        remaining = max(0, remaining - 1)
        if reduce_emi and balance > MONEY_TOLERANCE:
            next_rate = rate_on(add_months(due_date, 1), initial_rate, changes)
            current_emi = emi_amount(balance, max(1, remaining), next_rate)
        previous_due = due_date
        last_due_rate = due_rate

    repaid = rupee(sum(row.principal_component + row.part_prepayment for row in rows))
    variance = rupee(principal - repaid)
    continuity = all(
        abs(rows[i].opening_principal - rows[i - 1].closing_principal) <= 1
        for i in range(1, len(rows))
    )
    controls = {
        "initial_emi": original_emi,
        "total_interest": rupee(sum(row.interest_component for row in rows)),
        "total_prepayment": rupee(sum(row.part_prepayment for row in rows)),
        "principal_variance": variance,
        "payoff_date": rows[-1].due_date if rows else None,
        "schedule_rows": len(rows),
        "entered_tenure": tenure,
        "continuity": continuity,
        "paid_off": bool(rows and rows[-1].closing_principal == 0),
    }
    controls["status"] = "PASS" if controls["paid_off"] and continuity and abs(variance) <= 1 else "REVIEW"
    return rows, controls


def pre_emi_interest(principal, disbursement, first_emi, annual_rate):
    days = (as_date(first_emi) - as_date(disbursement)).days
    return rupee(max(0, float(principal) * float(annual_rate) * days / ANNUAL_BASIS))
