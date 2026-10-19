from __future__ import annotations
import math

ANNUAL_BASIS = 365
REGULAR_DAYS = 30

def periodic_rate(annual_roi: float) -> float:
    return annual_roi * REGULAR_DAYS / ANNUAL_BASIS

def calc_emi(principal: float, tenure: int, annual_roi: float) -> float:
    r = periodic_rate(annual_roi)
    if principal <= 0 or tenure <= 0: raise ValueError('Principal and tenure must be positive.')
    return principal / tenure if abs(r) < 1e-15 else principal * r / (1 - (1+r) ** (-tenure))

def calc_principal(emi: float, tenure: int, annual_roi: float) -> float:
    r = periodic_rate(annual_roi)
    if emi <= 0 or tenure <= 0: raise ValueError('EMI and tenure must be positive.')
    return emi * tenure if abs(r) < 1e-15 else emi * (1 - (1+r) ** (-tenure)) / r

def calc_tenure(principal: float, emi: float, annual_roi: float) -> int:
    r = periodic_rate(annual_roi)
    if principal <= 0 or emi <= 0: raise ValueError('Principal and EMI must be positive.')
    if abs(r) < 1e-15: return math.ceil(principal / emi)
    if emi <= principal*r: raise ValueError('EMI is insufficient to cover periodic interest.')
    return math.ceil(-math.log(1-principal*r/emi)/math.log(1+r))

def calc_roi(principal: float, tenure: int, emi: float) -> float:
    if principal <= 0 or tenure <= 0 or emi <= 0: raise ValueError('Principal, tenure and EMI must be positive.')
    lo, hi = 0.0, 1.0
    if emi < principal/tenure: raise ValueError('EMI is below the zero-interest EMI.')
    for _ in range(150):
        mid=(lo+hi)/2
        if calc_emi(principal,tenure,mid) < emi: lo=mid
        else: hi=mid
    return (lo+hi)/2

def solve_missing(target: str, principal: float, tenure: int, roi_pct: float, emi: float) -> dict:
    roi=roi_pct/100
    if target=='EMI': emi=calc_emi(principal,tenure,roi)
    elif target=='Principal': principal=calc_principal(emi,tenure,roi)
    elif target=='Tenure': tenure=calc_tenure(principal,emi,roi)
    elif target=='ROI': roi=calc_roi(principal,tenure,emi); roi_pct=roi*100
    else: raise ValueError('Invalid calculation target.')
    variance=calc_emi(principal,tenure,roi)-emi
    return {'principal':principal,'tenure':int(tenure),'roi_pct':roi_pct,'emi':emi,'control':'PASS' if abs(variance)<=0.01 else 'REVIEW','variance':variance}
