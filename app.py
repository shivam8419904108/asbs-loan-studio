from pathlib import Path
from datetime import date, timedelta
import base64, json, re
import pandas as pd
import streamlit as st
from supabase import create_client
from finance_engine import *
from exports import build_pdf, build_excel

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "assets" / "asbs-logo.png"
PAGES = ["EMI Calculator", "Repayment Schedule", "Saved Cases", "Profile"]
WIDGET_KEYS = ["schedule_name","schedule_account","schedule_case_name","schedule_principal","schedule_disbursement","schedule_first_emi","schedule_tenure","schedule_roi","schedule_mode"]

st.set_page_config(page_title="ASBS Loan Studio", page_icon="🏦", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--p:#680077;--p2:#9b00ab;--b:#e7dce9}.stApp{background:linear-gradient(145deg,#fbf9fc,#f4eef7)}
[data-testid=stMain] .block-container{max-width:1440px;padding:1.2rem 2rem 3rem;margin:auto}.hero{background:linear-gradient(125deg,var(--p),var(--p2));color:#fff;padding:1.6rem 1.9rem;border-radius:22px;margin-bottom:1.2rem;box-shadow:0 16px 36px #68007729}.hero h1{color:#fff;margin:0}.hero p{margin:.6rem 0 0}.logo-wrap{display:flex;justify-content:center;padding:.3rem 0 1rem}.logo{display:block;max-width:min(100%,330px);height:auto;max-height:105px;object-fit:contain;background:#fff;border-radius:14px;padding:8px 12px;box-sizing:border-box}.logo.side{max-height:82px;max-width:100%}section[data-testid=stSidebar]{background:linear-gradient(180deg,#fff,#f5eff7);border-right:1px solid var(--b)}[data-testid=stMetric]{background:#fff;border:1px solid var(--b);border-radius:15px;padding:.8rem}.stButton>button,.stDownloadButton>button{width:100%;min-height:44px;border-radius:11px;font-weight:700}.stButton>button[kind=primary]{background:linear-gradient(90deg,var(--p),var(--p2));color:#fff;border:0}input,textarea,[data-baseweb=select]{font-size:16px!important}[data-testid=stDataFrame]{border:1px solid var(--b);border-radius:14px;overflow:hidden}
@media(max-width:768px){[data-testid=stMain] .block-container{padding:.65rem .72rem 5rem}.hero{padding:1.1rem 1rem;border-radius:16px}.hero h1{font-size:1.42rem}.logo{width:min(100%,285px);max-height:none}[data-testid=stHorizontalBlock]{display:flex!important;flex-direction:column!important;gap:.5rem!important}[data-testid=stHorizontalBlock]>[data-testid=column]{width:100%!important;flex:1 1 100%!important;min-width:0!important}.stButton>button,.stDownloadButton>button{min-height:48px}section[data-testid=stSidebar]{width:min(86vw,310px)!important;min-width:min(86vw,310px)!important}}
</style>""", unsafe_allow_html=True)

def sb_client(): return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
def safe_name(v): return re.sub(r"[^A-Za-z0-9_-]+","_",str(v or "").strip()).strip("_") or "Loan"
def logo(side=False):
    if not LOGO.exists(): st.markdown("### ASBS & CO"); return
    b64=base64.b64encode(LOGO.read_bytes()).decode()
    st.markdown(f'<div class="logo-wrap"><img class="logo {"side" if side else ""}" src="data:image/png;base64,{b64}"></div>',unsafe_allow_html=True)

def normalize(case):
    p=case.get("payload") or {}
    if not isinstance(p,dict): p=json.loads(p)
    p=dict(p);p.setdefault("name",p.get("borrower",case.get("borrower","")));p.setdefault("account_number",p.get("ref",case.get("loan_reference","")));p.setdefault("case_name",case.get("case_name",p.get("case_name","Loan Schedule")));p.setdefault("roi_events",[]);p.setdefault("pp_events",[]);p.setdefault("roi_treatment","Recalculate EMI / Keep Tenure")
    return p

def calculate_payload(p):
    changes=[ROIChange(as_date(x["date"]),float(x["rate"])/100,x.get("note","")) for x in p.get("roi_events",[])]
    payments=[Prepayment(as_date(x["date"]),float(x["amount"]),x["effect"],x.get("note","")) for x in p.get("pp_events",[])]
    rows,ctl=generate_schedule(float(p["principal"]),as_date(p["disbursement"]),as_date(p["first_emi"]),int(p["tenure"]),float(p["roi"])/100,changes,payments,p.get("roi_treatment","Recalculate EMI / Keep Tenure"))
    pre=pre_emi_interest(float(p["principal"]),as_date(p["disbursement"]),as_date(p["first_emi"]),float(p["roi"])/100)
    return rows,ctl,pre,p

def clear_case():
    for k in ["loaded_case_id","loaded_payload","schedule_result","schedule_defaults",*WIDGET_KEYS]: st.session_state.pop(k,None)
    st.session_state.roi_events=[];st.session_state.pp_events=[]

def open_case(case):
    p=normalize(case);clear_case()
    st.session_state.loaded_case_id=case["id"];st.session_state.loaded_payload=p
    st.session_state.roi_events=p["roi_events"];st.session_state.pp_events=p["pp_events"]
    st.session_state.schedule_name=p.get("name","");st.session_state.schedule_account=p.get("account_number","");st.session_state.schedule_case_name=p.get("case_name","Loan Schedule");st.session_state.schedule_principal=float(p.get("principal",1_000_000));st.session_state.schedule_disbursement=as_date(p.get("disbursement",date.today()));st.session_state.schedule_first_emi=as_date(p.get("first_emi",date.today()+timedelta(days=30)));st.session_state.schedule_tenure=int(p.get("tenure",120));st.session_state.schedule_roi=float(p.get("roi",10));st.session_state.schedule_mode=p.get("roi_treatment","Recalculate EMI / Keep Tenure")
    st.session_state.schedule_result=calculate_payload(p)
    # Do not modify nav_page after its radio widget exists. Queue for next rerun.
    st.session_state.pending_nav_page="Repayment Schedule"

def auth_page(sb):
    logo();st.markdown('<div class="hero"><h1>ASBS Loan Studio</h1><p>Professional EMI calculation and repayment schedules.</p></div>',unsafe_allow_html=True)
    a,b,c=st.tabs(["Sign in","Create account","Forgot password"])
    with a:
        e=st.text_input("Email",key="le");p=st.text_input("Password",type="password",key="lp")
        if st.button("Sign in",type="primary"):
            try: st.session_state.auth=sb.auth.sign_in_with_password({"email":e,"password":p});st.rerun()
            except Exception as x: st.error(str(x))
    with b:
        e=st.text_input("Email",key="ce");p=st.text_input("Password",type="password",key="cp")
        if st.button("Create account"):
            try: sb.auth.sign_up({"email":e,"password":p});st.success("Account created. Confirm email if enabled, then sign in.")
            except Exception as x: st.error(str(x))
    with c:
        e=st.text_input("Registered email",key="fe")
        if st.button("Send reset email"):
            try: sb.auth.reset_password_email(e,{"redirect_to":"https://asbs-loan.streamlit.app"});st.success("Recovery email sent.")
            except Exception as x: st.error(str(x))

def emi_page():
    st.markdown('<div class="hero"><h1>EMI Calculator</h1><p>Enter any three values. Annual basis: 365 days.</p></div>',unsafe_allow_html=True)
    target=st.selectbox("Calculate",["EMI","Principal","Tenure","ROI"])
    with st.form("emi"):
        a,b=st.columns(2);principal=a.number_input("Loan Principal (₹)",0.0,1e12,5_451_215.0,10_000.0,format="%.2f",disabled=target=="Principal");tenure=b.number_input("Tenure (months)",0,600,45,1,disabled=target=="Tenure")
        a,b=st.columns(2);roi=a.number_input("ROI (% p.a.)",0.0,100.0,8.75,.5,format="%.2f",disabled=target=="ROI");emi=b.number_input("EMI (₹)",0.0,1e12,0.0,1000.0,format="%.2f",disabled=target=="EMI")
        run=st.form_submit_button("Calculate",type="primary")
    if run:
        try: st.session_state.emi_result=solve_missing(target,principal,int(tenure),roi,emi)
        except Exception as x: st.error(str(x))
    r=st.session_state.get("emi_result")
    if r:
        c=st.columns(4);c[0].metric("Principal",f"₹{r['principal']:,.2f}");c[1].metric("Tenure",f"{r['tenure']} months");c[2].metric("ROI",f"{r['roi_pct']:.2f}%");c[3].metric("EMI",f"₹{r['emi']:,.2f}")
        if st.button("Use in Repayment Schedule"): clear_case();st.session_state.schedule_defaults=r;st.session_state.pending_nav_page="Repayment Schedule";st.rerun()

def events_ui():
    t1,t2=st.tabs(["ROI Changes","Part Payments"])
    with t1:
        with st.form("roi_event",clear_on_submit=True):
            a,b,c=st.columns(3);d=a.date_input("Effective date");r=b.number_input("New ROI (%)",0.0,100.0,10.0,.5,format="%.2f");n=c.text_input("Note")
            if st.form_submit_button("Add ROI change"): st.session_state.roi_events.append({"date":d.isoformat(),"rate":r,"note":n});st.session_state.schedule_result=None;st.rerun()
        for i,x in enumerate(st.session_state.roi_events):
            a,b=st.columns([8,1]);a.info(f"{x['date']} · {x['rate']:.2f}% · {x.get('note') or 'No note'}")
            if b.button("Remove",key=f"rr{i}"): st.session_state.roi_events.pop(i);st.session_state.schedule_result=None;st.rerun()
    with t2:
        with st.form("pp_event",clear_on_submit=True):
            a,b,c,d=st.columns(4);day=a.date_input("Payment date");amt=b.number_input("Amount (₹)",.01,step=1000.0,format="%.2f");effect=c.selectbox("Effect",["Reduce Tenure","Reduce EMI"]);note=d.text_input("Note")
            if st.form_submit_button("Add part-payment"): st.session_state.pp_events.append({"date":day.isoformat(),"amount":amt,"effect":effect,"note":note});st.session_state.schedule_result=None;st.rerun()
        for i,x in enumerate(st.session_state.pp_events):
            a,b=st.columns([8,1]);a.info(f"{x['date']} · ₹{x['amount']:,.2f} · {x['effect']}")
            if b.button("Remove",key=f"rp{i}"): st.session_state.pp_events.pop(i);st.session_state.schedule_result=None;st.rerun()

def schedule_page(sb,user):
    d=st.session_state.get("schedule_defaults",{});p=st.session_state.get("loaded_payload",{})
    st.markdown('<div class="hero"><h1>Repayment Schedule</h1><p>Open, edit, recalculate, export and save the complete case.</p></div>',unsafe_allow_html=True)
    st.session_state.setdefault("schedule_name",p.get("name",""));st.session_state.setdefault("schedule_account",p.get("account_number",""));st.session_state.setdefault("schedule_case_name",p.get("case_name","Loan Schedule"));st.session_state.setdefault("schedule_principal",float(p.get("principal",d.get("principal",1_000_000))));st.session_state.setdefault("schedule_disbursement",as_date(p["disbursement"]) if p.get("disbursement") else date.today());st.session_state.setdefault("schedule_first_emi",as_date(p["first_emi"]) if p.get("first_emi") else date.today()+timedelta(days=30));st.session_state.setdefault("schedule_tenure",int(p.get("tenure",d.get("tenure",120))));st.session_state.setdefault("schedule_roi",float(p.get("roi",d.get("roi_pct",10))));st.session_state.setdefault("schedule_mode",p.get("roi_treatment","Recalculate EMI / Keep Tenure"))
    a,b,c=st.columns(3);name=a.text_input("Name",key="schedule_name");account=b.text_input("Account Number",key="schedule_account");case_name=c.text_input("Case Name",key="schedule_case_name")
    a,b,c=st.columns(3);principal=a.number_input("Principal (₹)",min_value=1.0,step=10000.0,format="%.2f",key="schedule_principal");disb=b.date_input("Disbursement Date",key="schedule_disbursement");first=c.date_input("First EMI Date",key="schedule_first_emi")
    a,b,c=st.columns(3);tenure=a.number_input("Tenure (months)",min_value=1,max_value=600,step=1,key="schedule_tenure");roi=b.number_input("Initial ROI (%)",min_value=0.0,max_value=100.0,step=.5,format="%.2f",key="schedule_roi");mode=c.selectbox("ROI Treatment",["Recalculate EMI / Keep Tenure","Keep EMI / Reduce Tenure"],key="schedule_mode")
    events_ui();a,b=st.columns([3,1]);recalc=a.button("Recalculate Schedule",type="primary")
    if b.button("Start New Case"): clear_case();st.rerun()
    if recalc:
        payload={"case_name":case_name.strip() or "Loan Schedule","name":name.strip(),"account_number":account.strip(),"principal":rupee(principal),"disbursement":disb.isoformat(),"first_emi":first.isoformat(),"tenure":int(tenure),"roi":float(roi),"roi_treatment":mode,"roi_events":st.session_state.roi_events,"pp_events":st.session_state.pp_events}
        try: st.session_state.loaded_payload=payload;st.session_state.schedule_result=calculate_payload(payload)
        except Exception as x: st.error(str(x))
    result=st.session_state.get("schedule_result")
    if not result: st.info("Edit inputs or events, then select Recalculate Schedule.");return
    rows,ctl,pre,payload=result;payload=dict(payload);payload.update({"name":name.strip(),"account_number":account.strip(),"case_name":case_name.strip() or "Loan Schedule"});st.session_state.schedule_result=(rows,ctl,pre,payload)
    cols=st.columns(7);vals=[("Initial EMI",f"₹{ctl['initial_emi']:,.2f}"),("Interest",f"₹{ctl['total_interest']:,.2f}"),("Part Payments",f"₹{ctl['total_prepayment']:,.2f}"),("Variance",f"₹{ctl['principal_variance']:,.2f}"),("Schedule Rows",str(ctl['schedule_rows'])),("Payoff",ctl['payoff_date'].strftime("%d-%m-%Y")),("Control",ctl['status'])]
    for col,(k,v) in zip(cols,vals): col.metric(k,v)
    df=pd.DataFrame([{"EMI #":r.emi_no,"Due Date":r.due_date,"Opening Principal":r.opening_principal,"ROI (% p.a.)":r.roi*100,"Interest Component":r.interest_component,"Principal Component":r.principal_component,"EMI":r.emi,"Part Prepayment":r.part_prepayment,"Closing Principal":r.closing_principal} for r in rows]);money=["Opening Principal","Interest Component","Principal Component","EMI","Part Prepayment","Closing Principal"];cfg={x:st.column_config.NumberColumn(format="₹ %.2f") for x in money};cfg["ROI (% p.a.)"]=st.column_config.NumberColumn(format="%.2f");st.dataframe(df,use_container_width=True,hide_index=True,column_config=cfg)
    pdf=build_pdf(LOGO,payload,pre,ctl,rows);xlsx=build_excel(payload,pre,ctl,rows,st.session_state.roi_events,st.session_state.pp_events);base=f"ASBS_RPS_{safe_name(payload['account_number'])}";btn=st.columns(3);btn[0].download_button("Download PDF",pdf,f"{base}.pdf","application/pdf");btn[1].download_button("Download Excel",xlsx,f"{base}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if btn[2].button("Save Changes" if st.session_state.get("loaded_case_id") else "Save Case"):
        rec={"user_id":user.id,"case_name":payload["case_name"],"borrower":payload["name"],"loan_reference":payload["account_number"],"payload":payload}
        try:
            cid=st.session_state.get("loaded_case_id")
            if cid: sb.table("loan_cases").update(rec).eq("id",cid).execute()
            else:
                out=sb.table("loan_cases").insert(rec).execute()
                if out.data: st.session_state.loaded_case_id=out.data[0]["id"]
            st.session_state.loaded_payload=payload;st.success("Case saved with complete calculation.")
        except Exception as x: st.error(f"Save failed: {x}")

def saved_page(sb,user):
    st.markdown('<div class="hero"><h1>Saved Cases</h1><p>Search, open the complete calculation, edit and recalculate.</p></div>',unsafe_allow_html=True);q=st.text_input("Search by Account Number or Name")
    try: cases=sb.table("loan_cases").select("*").eq("user_id",user.id).order("updated_at",desc=True).execute().data
    except Exception as x: st.error(str(x));return
    q=q.strip().lower()
    if q: cases=[x for x in cases if q in str(x.get("loan_reference","")).lower() or q in str(x.get("borrower","")).lower() or q in str(x.get("case_name","")).lower()]
    st.caption(f"{len(cases)} case(s) found")
    for case in cases:
        a,b,c=st.columns([5,1,1]);a.markdown(f"**Account: {case.get('loan_reference') or '-'}**  \nName: {case.get('borrower') or '-'} · {case.get('case_name') or '-'}")
        if b.button("Open / Edit",key=f"o{case['id']}"):
            try: open_case(case);st.rerun()
            except Exception as x: st.error(f"Could not open calculation: {x}")
        if c.button("Delete",key=f"d{case['id']}"): sb.table("loan_cases").delete().eq("id",case["id"]).execute();st.rerun()

def main(sb):
    # Apply queued navigation before the radio widget is instantiated.
    if "pending_nav_page" in st.session_state: st.session_state.nav_page=st.session_state.pop("pending_nav_page")
    st.session_state.setdefault("nav_page","EMI Calculator");st.session_state.setdefault("roi_events",[]);st.session_state.setdefault("pp_events",[]);user=st.session_state.auth.user
    with st.sidebar:
        logo(True);st.radio("Workspace",PAGES,key="nav_page");st.caption(user.email)
        if st.button("Sign out"): sb.auth.sign_out();st.session_state.clear();st.rerun()
    {"EMI Calculator":lambda:emi_page(),"Repayment Schedule":lambda:schedule_page(sb,user),"Saved Cases":lambda:saved_page(sb,user),"Profile":lambda:st.write(user.email)}[st.session_state.nav_page]()

sb=sb_client()
if "auth" in st.session_state:
    try:
        s=st.session_state.auth.session;r=sb.auth.set_session(s.access_token,s.refresh_token)
        if r and r.session: st.session_state.auth=r
    except Exception: st.session_state.pop("auth",None);st.rerun()
if "auth" not in st.session_state: auth_page(sb)
else: main(sb)
