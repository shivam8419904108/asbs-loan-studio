from dataclasses import dataclass
from datetime import date, datetime
from calendar import monthrange

@dataclass(frozen=True)
class ROIChange: effective_date: date; annual_rate: float; note: str=''
@dataclass(frozen=True)
class Prepayment: event_date: date; amount: float; effect: str; note: str=''
@dataclass
class Row:
    emi_no:int; due_date:date; opening_principal:float; roi:float; interest_component:float; principal_component:float; emi:float; part_prepayment:float; closing_principal:float

def as_date(v):
    if v is None:return None
    if isinstance(v,datetime):return v.date()
    if isinstance(v,date):return v
    if hasattr(v,'to_pydatetime'):return v.to_pydatetime().date()
    return datetime.fromisoformat(str(v)[:10]).date()
def add_months(d,n):
    m=d.month-1+n;y=d.year+m//12;m=m%12+1
    return date(y,m,min(d.day,monthrange(y,m)[1]))
def pmt(p,r,n):
    x=r/12
    return p/n if abs(x)<1e-12 else p*x/(1-(1+x)**(-n))
def rate_on(d,initial,changes):
    r=initial
    for c in sorted(changes,key=lambda z:z.effective_date):
        if c.effective_date<=d:r=c.annual_rate
        else:break
    return r
def accrued_interest(balance,start,end,initial,changes,prepayments,basis=360):
    """Actual-day interest, splitting at every ROI and prepayment event in [start,end)."""
    events=[]
    for c in changes:
        if start<c.effective_date<end:events.append((c.effective_date,'rate',c))
    for i,p in enumerate(prepayments):
        if start<=p.event_date<end:events.append((p.event_date,'pp',(i,p)))
    events.sort(key=lambda x:(x[0],0 if x[1]=='rate' else 1))
    cursor=start;rate=rate_on(start,initial,changes);bal=balance;interest=0;applied=[]
    for day,kind,obj in events:
        interest+=bal*rate*(day-cursor).days/basis;cursor=day
        if kind=='rate':rate=obj.annual_rate
        else:
            i,p=obj;amt=min(bal,p.amount);bal-=amt;applied.append((i,amt,p.effect))
    interest+=bal*rate*(end-cursor).days/basis
    return max(0,interest),applied

def generate(principal,disb,first,tenure,initial,changes,pps,roi_mode='Keep EMI / Reduce tenure',basis=360):
    disb,first=as_date(disb),as_date(first)
    changes=sorted([ROIChange(as_date(c.effective_date),float(c.annual_rate),c.note) for c in changes],key=lambda x:x.effective_date)
    pps=sorted([Prepayment(as_date(p.event_date),float(p.amount),p.effect,p.note) for p in pps],key=lambda x:x.event_date)
    if principal<=0 or tenure<=0:raise ValueError('Principal and tenure must be positive.')
    if first<disb:raise ValueError('First EMI cannot be before disbursement.')
    if any(not 0<=c.annual_rate<=1 for c in changes):raise ValueError('ROI must be between 0% and 100%.')
    bal=float(principal);remaining=int(tenure);emi=pmt(bal,rate_on(first,initial,changes),remaining);rows=[];used=set();prev=add_months(first,-1);last_due_rate=rate_on(first,initial,changes)
    for n in range(1,tenure+601):
        if bal<=.005:break
        due=add_months(first,n-1);opening=bal;due_rate=rate_on(due,initial,changes)
        if roi_mode=='Recalculate EMI' and abs(due_rate-last_due_rate)>1e-12:emi=pmt(opening,due_rate,max(1,remaining))
        period_pp=[p for i,p in enumerate(pps) if i not in used]
        interest,applied=accrued_interest(opening,prev,due,initial,changes,period_pp,basis)
        pp_total=0;reduce_emi=False
        for local_i,amt,effect in applied:
            target=period_pp[local_i]
            original_i=pps.index(target);used.add(original_i);pp_total+=amt;reduce_emi|=effect=='Reduce EMI'
        available=max(0,opening-pp_total);principal_component=max(0,min(available,emi-interest));closing=max(0,available-principal_component)
        cash_emi=interest+principal_component if closing<=.005 else emi
        if closing<=.005:closing=0
        rows.append(Row(n,due,opening,due_rate,interest,principal_component,cash_emi,pp_total,closing))
        bal=closing;remaining=max(0,remaining-1)
        if reduce_emi and bal>0:emi=pmt(bal,rate_on(add_months(due,1),initial,changes),max(1,remaining))
        prev=due;last_due_rate=due_rate
    principal_repaid=sum(r.principal_component+r.part_prepayment for r in rows)
    continuity=all(abs(rows[i].opening_principal-rows[i-1].closing_principal)<.02 for i in range(1,len(rows)))
    controls={'initial_emi':pmt(principal,initial,tenure),'total_interest':sum(r.interest_component for r in rows),'total_prepayment':sum(r.part_prepayment for r in rows),'principal_repaid':principal_repaid,'principal_variance':principal-principal_repaid,'payoff_date':rows[-1].due_date if rows else None,'continuity':continuity,'paid_off':bool(rows and rows[-1].closing_principal==0)}
    controls['status']='PASS' if controls['paid_off'] and continuity and abs(controls['principal_variance'])<.02 else 'REVIEW'
    return rows,controls
def pre_emi(principal,disb,first,roi,basis=360):return max(0,principal*roi*(as_date(first)-as_date(disb)).days/basis)
