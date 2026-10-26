from datetime import date
from finance_engine import *

def test_reference_emi():
    assert emi_amount(5_451_215,45,.0875)==142227

def test_roi_above_100_not_capped():
    r=solve_missing("ROI",512325,120,0,44511)
    assert 105.69 < r["roi_pct"] < 105.71
    assert r["control"]=="PASS"
    assert r["warning"]

def test_roi_standard():
    e=emi_amount(1_000_000,120,.10)
    r=solve_missing("ROI",1_000_000,120,0,e)
    assert abs(r["roi_pct"]-10)<.02

def test_exact_tenure_240():
    rows,c=generate_schedule(5_000_000,date(2026,1,1),date(2026,2,1),240,.0875)
    assert len(rows)==240 and c["status"]=="PASS" and c["principal_variance"]==0

def test_zero_rate():
    rows,c=generate_schedule(1200,date(2026,1,1),date(2026,2,1),12,0)
    assert len(rows)==12 and rows[0].emi==100 and c["status"]=="PASS"

def test_reduce_tenure():
    rows,c=generate_schedule(1_000_000,date(2026,1,1),date(2026,2,1),120,.10,prepayments=[Prepayment(date(2027,1,15),500000,"Reduce Tenure")],roi_treatment="Keep EMI / Reduce Tenure")
    assert len(rows)<120 and c["status"]=="PASS"

def test_reduce_emi():
    rows,c=generate_schedule(1_000_000,date(2026,1,1),date(2026,2,1),120,.10,prepayments=[Prepayment(date(2027,1,15),100000,"Reduce EMI")])
    assert len(rows)==120 and c["status"]=="PASS"

def test_roi_and_prepayment_same_day():
    rows,c=generate_schedule(1_000_000,date(2026,1,1),date(2026,2,1),120,.10,[ROIChange(date(2027,1,15),.12)],[Prepayment(date(2027,1,15),100000,"Reduce EMI")])
    assert c["total_prepayment"]==100000 and c["status"]=="PASS"

def test_month_end_dates():
    rows,_=generate_schedule(100000,date(2026,1,1),date(2026,1,31),3,.10)
    assert [x.due_date for x in rows]==[date(2026,1,31),date(2026,2,28),date(2026,3,31)]

def test_rounding():
    assert rupee(711293.3844)==711293.0
    assert rupee(711293.6)==711294.0
