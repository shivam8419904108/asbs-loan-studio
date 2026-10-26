from datetime import date
from finance_engine import *
def test_round_whole_rupee():assert rupee(711293.3844)==711293.0 and rupee(10.6)==11.0
def test_240():
 rows,c=generate_schedule(5_000_000,date(2026,1,1),date(2026,2,1),240,.0875);assert len(rows)==240 and c['status']=='PASS' and all(x.opening_principal==int(x.opening_principal) for x in rows)
def test_roi_pp():
 rows,c=generate_schedule(1_000_000,date(2026,1,1),date(2026,2,1),120,.10,[ROIChange(date(2027,2,15),.12)],[Prepayment(date(2027,2,15),100_000,'Reduce EMI')]);assert c['status']=='PASS' and c['total_prepayment']==100000
def test_reduce_tenure():
 rows,c=generate_schedule(1_000_000,date(2026,1,1),date(2026,2,1),120,.10,prepayments=[Prepayment(date(2027,1,15),500000,'Reduce Tenure')],roi_treatment='Keep EMI / Reduce Tenure');assert len(rows)<120 and c['status']=='PASS'
def test_zero():
 rows,c=generate_schedule(1200,date(2026,1,1),date(2026,2,1),12,0);assert len(rows)==12 and rows[0].emi==100 and c['status']=='PASS'
