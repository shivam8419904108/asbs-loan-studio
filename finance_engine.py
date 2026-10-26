from dataclasses import dataclass
from datetime import date, datetime
from calendar import monthrange
import math

ANNUAL_BASIS = 365
REGULAR_DAYS = 30
TOLERANCE = 1.0

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
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    return datetime.fromisoformat(str(value)[:10]).date()

def add_months(day, months):
    idx = day.month - 1 + months
    year, month = day.year + idx // 12, idx % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))

def rupee(value):
    """Loan statement convention: nearest whole rupee, represented as x.00."""
    return float(round(float(value)))

def periodic_rate(annual_rate): return annual_rate * REGULAR_DAYS / ANNUAL_BASIS

def emi_amount(principal, tenure, annual_rate):
    if principal <= 0 or tenure <= 0: raise ValueError("Principal and tenure must be positive.")
    rate = periodic_rate(annual_rate)
    raw = principal / tenure if abs(rate) < 1e-15 else principal * rate / (1 - (1 + rate) ** (-tenure))
    return rupee(raw)

def principal_from_emi(emi, tenure, annual_rate):
    if emi <= 0 or tenure <= 0: raise ValueError("EMI and tenure must be positive.")
    r = periodic_rate(annual_rate)
    return rupee(emi * tenure if abs(r) < 1e-15 else emi * (1 - (1+r) ** (-tenure)) / r)

def tenure_from_emi(principal, emi, annual_rate):
    r = periodic_rate(annual_rate)
    if emi <= principal * r: raise ValueError("EMI is insufficient to cover periodic interest.")
    return math.ceil(principal / emi) if abs(r) < 1e-15 else math.ceil(-math.log(1-principal*r/emi)/math.log(1+r))

def roi_from_emi(principal, tenure, emi):
    if emi < principal / tenure: raise ValueError("EMI is below the zero-interest EMI.")
    lo, hi = 0.0, 1.0
    for _ in range(180):
        mid = (lo + hi) / 2
        if emi_amount(principal, tenure, mid) < emi: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def solve_missing(target, principal, tenure, roi_pct, emi):
    annual = roi_pct / 100
    if target == "EMI": emi = emi_amount(principal, tenure, annual)
    elif target == "Principal": principal = principal_from_emi(emi, tenure, annual)
    elif target == "Tenure": tenure = tenure_from_emi(principal, emi, annual)
    elif target == "ROI": annual = roi_from_emi(principal, tenure, emi); roi_pct = annual * 100
    variance = emi_amount(principal, int(tenure), annual) - rupee(emi)
    return {"principal":rupee(principal),"tenure":int(tenure),"roi_pct":roi_pct,"emi":rupee(emi),"variance":rupee(variance),"control":"PASS" if abs(variance)<=1 else "REVIEW"}

def rate_on(day, initial, changes):
    rate = initial
    for change in sorted(changes, key=lambda x:x.effective_date):
        if change.effective_date <= day: rate = change.annual_rate
        else: break
    return rate

def period_interest(opening, start, end, initial, changes, available_payments):
    events=[]
    for change in changes:
        if start < change.effective_date < end: events.append((change.effective_date,0,"rate",change))
    for idx,payment in available_payments:
        if start <= payment.event_date < end: events.append((payment.event_date,1,"payment",(idx,payment)))
    events.sort(key=lambda x:(x[0],x[1]))
    cursor=start; rate=rate_on(start,initial,changes); balance=opening; interest=0.0; applied=[]
    for event_day,_,kind,event in events:
        interest += balance*rate*(event_day-cursor).days/ANNUAL_BASIS; cursor=event_day
        if kind=="rate": rate=event.annual_rate
        else:
            idx,payment=event; amount=min(balance,rupee(payment.amount)); balance-=amount; applied.append((idx,amount,payment.effect))
    interest += balance*rate*(end-cursor).days/ANNUAL_BASIS
    return rupee(max(0,interest)), applied

def generate_schedule(principal, disbursement, first_emi, tenure, initial_rate, changes=(), prepayments=(), roi_treatment="Recalculate EMI / Keep Tenure"):
    principal=rupee(principal); disbursement,first_emi=as_date(disbursement),as_date(first_emi)
    if first_emi < disbursement: raise ValueError("First EMI date cannot be before disbursement date.")
    changes=sorted([ROIChange(as_date(c.effective_date),float(c.annual_rate),c.note) for c in changes],key=lambda x:x.effective_date)
    payments=sorted([Prepayment(as_date(p.event_date),rupee(p.amount),p.effect,p.note) for p in prepayments],key=lambda x:x.event_date)
    balance=principal; remaining=int(tenure); current_emi=emi_amount(balance,remaining,initial_rate); original_emi=current_emi
    previous=add_months(first_emi,-1); last_rate=rate_on(first_emi,initial_rate,changes); used=set(); rows=[]
    for no in range(1,int(tenure)+1):
        if balance <= TOLERANCE: break
        due=add_months(first_emi,no-1); opening=rupee(balance); due_rate=rate_on(due,initial_rate,changes)
        if roi_treatment=="Recalculate EMI / Keep Tenure" and abs(due_rate-last_rate)>1e-15:
            current_emi=emi_amount(opening,max(1,remaining),due_rate)
        interest,applied=period_interest(opening,previous,due,initial_rate,changes,[(i,p) for i,p in enumerate(payments) if i not in used])
        pp_total=0.0; reduce_emi=False
        for idx,amount,effect in applied: used.add(idx); pp_total+=amount; reduce_emi = reduce_emi or effect=="Reduce EMI"
        pp_total=rupee(pp_total); available=rupee(max(0,opening-pp_total))
        if no==int(tenure):
            principal_component=available; cash_emi=rupee(interest+principal_component); closing=0.0
        else:
            principal_component=rupee(max(0,min(available,current_emi-interest)))
            closing=rupee(max(0,available-principal_component))
            cash_emi=rupee(interest+principal_component) if closing<=TOLERANCE else current_emi
            if closing<=TOLERANCE: closing=0.0
        rows.append(ScheduleRow(no,due,opening,due_rate,interest,principal_component,cash_emi,pp_total,closing))
        balance=closing; remaining=max(0,remaining-1)
        if reduce_emi and balance>TOLERANCE: current_emi=emi_amount(balance,max(1,remaining),rate_on(add_months(due,1),initial_rate,changes))
        previous=due; last_rate=due_rate
    repaid=rupee(sum(r.principal_component+r.part_prepayment for r in rows)); variance=rupee(principal-repaid)
    continuity=all(abs(rows[i].opening_principal-rows[i-1].closing_principal)<=1 for i in range(1,len(rows)))
    controls={"initial_emi":original_emi,"total_interest":rupee(sum(r.interest_component for r in rows)),"total_prepayment":rupee(sum(r.part_prepayment for r in rows)),"principal_variance":variance,"payoff_date":rows[-1].due_date if rows else None,"schedule_rows":len(rows),"entered_tenure":int(tenure),"continuity":continuity,"paid_off":bool(rows and rows[-1].closing_principal==0)}
    controls["status"]="PASS" if controls["paid_off"] and continuity and abs(variance)<=1 else "REVIEW"
    return rows,controls

def pre_emi_interest(principal, disbursement, first_emi, annual_rate):
    return rupee(max(0,principal*annual_rate*(as_date(first_emi)-as_date(disbursement)).days/ANNUAL_BASIS))
