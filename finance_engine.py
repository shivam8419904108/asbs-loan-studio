from dataclasses import dataclass
from datetime import date, datetime
from calendar import monthrange
import math
ANNUAL_BASIS=365
REGULAR_DAYS=30
@dataclass(frozen=True)
class ROIChange: effective_date:date; annual_rate:float; note:str=''
@dataclass(frozen=True)
class Prepayment: event_date:date; amount:float; effect:str; note:str=''
@dataclass
class Row:
    emi_no:int; due_date:date; opening_principal:float; roi:float; interest_component:float; principal_component:float; emi:float; part_prepayment:float; closing_principal:float

def as_date(v):
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    return datetime.fromisoformat(str(v)[:10]).date()
def add_months(d,n):
    m=d.month-1+n;y=d.year+m//12;m=m%12+1
    return date(y,m,min(d.day,monthrange(y,m)[1]))
def periodic_rate(annual): return annual*REGULAR_DAYS/ANNUAL_BASIS
def calc_emi(p,n,annual):
    if p<=0 or n<=0: raise ValueError('Principal and tenure must be positive.')
    r=periodic_rate(annual)
    return p/n if abs(r)<1e-14 else p*r/(1-(1+r)**(-n))
def calc_principal(emi,n,annual):
    r=periodic_rate(annual)
    return emi*n if abs(r)<1e-14 else emi*(1-(1+r)**(-n))/r
def calc_tenure(p,emi,annual):
    r=periodic_rate(annual)
    if emi<=p*r: raise ValueError('EMI is insufficient to cover periodic interest.')
    return math.ceil(p/emi) if abs(r)<1e-14 else math.ceil(-math.log(1-p*r/emi)/math.log(1+r))
def calc_roi(p,n,emi):
    if emi<p/n: raise ValueError('EMI is below the zero-interest EMI.')
    lo,hi=0.0,1.0
    for _ in range(160):
        mid=(lo+hi)/2
        if calc_emi(p,n,mid)<emi:lo=mid
        else:hi=mid
    return (lo+hi)/2
def solve_missing(target,p,n,roi_pct,emi):
    annual=roi_pct/100
    if target=='EMI':emi=calc_emi(p,n,annual)
    elif target=='Principal':p=calc_principal(emi,n,annual)
    elif target=='Tenure':n=calc_tenure(p,emi,annual)
    elif target=='ROI':annual=calc_roi(p,n,emi);roi_pct=annual*100
    variance=calc_emi(p,int(n),annual)-emi
    return {'principal':p,'tenure':int(n),'roi_pct':roi_pct,'emi':emi,'variance':variance,'control':'PASS' if abs(variance)<=.01 else 'REVIEW'}
def rate_on(d,initial,changes):
    r=initial
    for c in sorted(changes,key=lambda x:x.effective_date):
        if c.effective_date<=d:r=c.annual_rate
        else:break
    return r
def period_interest(opening,start,end,initial,changes,pps):
    events=[]
    for c in changes:
        if start<c.effective_date<end:events.append((c.effective_date,0,'rate',c))
    for idx,p in pps:
        if start<=p.event_date<end:events.append((p.event_date,1,'pp',(idx,p)))
    events.sort(key=lambda x:(x[0],x[1]));cursor=start;rate=rate_on(start,initial,changes);bal=opening;interest=0;applied=[]
    for day,_,kind,obj in events:
        interest+=bal*rate*(day-cursor).days/ANNUAL_BASIS;cursor=day
        if kind=='rate':rate=obj.annual_rate
        else:
            idx,p=obj;amt=min(bal,p.amount);bal-=amt;applied.append((idx,amt,p.effect))
    interest+=bal*rate*(end-cursor).days/ANNUAL_BASIS
    return max(0,interest),applied

def generate_schedule(principal,disb,first,tenure,initial,changes=(),prepayments=(),roi_mode='Keep EMI / Reduce tenure'):
    disb,first=as_date(disb),as_date(first)
    if first<disb:raise ValueError('First EMI date cannot be before disbursement date.')
    changes=sorted([ROIChange(as_date(c.effective_date),c.annual_rate,c.note) for c in changes],key=lambda x:x.effective_date)
    pps=sorted([Prepayment(as_date(p.event_date),p.amount,p.effect,p.note) for p in prepayments],key=lambda x:x.event_date)
    balance=float(principal);remaining=int(tenure);current_emi=calc_emi(balance,remaining,rate_on(first,initial,changes));rows=[];used=set();previous=add_months(first,-1);last_due_rate=rate_on(first,initial,changes)
    for no in range(1,tenure+601):
        if balance<=.005:break
        due=add_months(first,no-1);opening=balance;due_rate=rate_on(due,initial,changes)
        if roi_mode=='Recalculate EMI' and abs(due_rate-last_due_rate)>1e-12:current_emi=calc_emi(opening,max(1,remaining),due_rate)
        available_pp=[(i,p) for i,p in enumerate(pps) if i not in used]
        interest,applied=period_interest(opening,previous,due,initial,changes,available_pp)
        pp_total=0;reduce_emi=False
        for idx,amt,effect in applied:used.add(idx);pp_total+=amt;reduce_emi=reduce_emi or effect=='Reduce EMI'
        available=max(0,opening-pp_total);principal_component=max(0,min(available,current_emi-interest));closing=max(0,available-principal_component)
        cash_emi=interest+principal_component if closing<=.005 else current_emi
        if closing<=.005:closing=0
        rows.append(Row(no,due,opening,due_rate,interest,principal_component,cash_emi,pp_total,closing))
        balance=closing;remaining=max(0,remaining-1)
        if reduce_emi and balance>0:current_emi=calc_emi(balance,max(1,remaining),rate_on(add_months(due,1),initial,changes))
        previous=due;last_due_rate=due_rate
    repaid=sum(r.principal_component+r.part_prepayment for r in rows);variance=principal-repaid
    continuity=all(abs(rows[i].opening_principal-rows[i-1].closing_principal)<.02 for i in range(1,len(rows)))
    ctl={'initial_emi':calc_emi(principal,tenure,initial),'total_interest':sum(r.interest_component for r in rows),'total_prepayment':sum(r.part_prepayment for r in rows),'principal_variance':0 if abs(variance)<.005 else variance,'payoff_date':rows[-1].due_date if rows else None,'continuity':continuity,'paid_off':bool(rows and rows[-1].closing_principal==0)}
    ctl['status']='PASS' if ctl['paid_off'] and continuity and abs(variance)<.02 else 'REVIEW'
    return rows,ctl
def pre_emi(principal,disb,first,annual):return max(0,principal*annual*(as_date(first)-as_date(disb)).days/ANNUAL_BASIS)
