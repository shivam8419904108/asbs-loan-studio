from pathlib import Path
from datetime import date,timedelta
import json,re,base64
import pandas as pd
import streamlit as st
from supabase import create_client
from finance_engine import *
from exports import build_pdf,build_excel
ROOT=Path(__file__).resolve().parent;LOGO=ROOT/'assets/asbs-logo.png'
st.set_page_config(page_title='ASBS Loan Studio',page_icon='🏦',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
:root{
  --asbs-purple:#680077;--asbs-magenta:#9b00ab;--asbs-blue:#185a8d;
  --surface:#ffffff;--background:#f7f4f8;--border:#e7dce9;--text:#231426;--muted:#6d6170;
}
html,body,[class*="css"]{font-family:Inter,"Segoe UI",Arial,sans-serif;color:var(--text)}
.stApp{background:linear-gradient(145deg,#fbf9fc 0%,#f4eef7 100%)}
[data-testid="stMain"] .block-container{width:min(100%,1440px);max-width:1440px;padding:1.25rem 2rem 3rem;margin:0 auto}
[data-testid="stHeader"]{background:rgba(255,255,255,.88);backdrop-filter:blur(12px);border-bottom:1px solid rgba(104,0,119,.08)}
.hero{background:linear-gradient(125deg,var(--asbs-purple),var(--asbs-magenta));color:#fff;padding:1.75rem 2rem;border-radius:22px;margin:0 0 1.25rem;box-shadow:0 16px 36px rgba(104,0,119,.16)}
.hero h1{color:#fff;margin:0;font-size:clamp(1.55rem,3vw,2.45rem);line-height:1.15}.hero p{margin:.7rem 0 0;font-size:clamp(.92rem,1.4vw,1.08rem);opacity:.94}
.asbs-logo-wrap{display:flex;align-items:center;justify-content:flex-start;width:100%;padding:.35rem 0 1rem;overflow:visible}
.asbs-logo-wrap.center{justify-content:center;padding:.5rem 0 1.25rem}
.asbs-logo{display:block;width:auto;max-width:min(100%,330px);height:auto;max-height:105px;object-fit:contain;object-position:center;background:#fff;border-radius:14px;padding:8px 12px;box-sizing:border-box;box-shadow:0 6px 18px rgba(40,20,45,.08)}
.asbs-logo.sidebar{max-width:100%;max-height:82px;padding:6px 8px}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#fff 0%,#f5eff7 100%);border-right:1px solid var(--border)}
section[data-testid="stSidebar"]>div{padding-top:1rem}
section[data-testid="stSidebar"] [role="radiogroup"]{gap:.22rem}
section[data-testid="stSidebar"] label[data-baseweb="radio"]{padding:.58rem .65rem;border-radius:10px}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{background:#efe4f2}
[data-testid="stForm"],div[data-testid="stVerticalBlockBorderWrapper"]{background:rgba(255,255,255,.9);border:1px solid var(--border);border-radius:17px;padding:.4rem;box-shadow:0 7px 22px rgba(62,30,70,.05)}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--border);border-radius:15px;padding:.85rem 1rem;box-shadow:0 5px 16px rgba(62,30,70,.05)}
[data-testid="stMetricValue"]{font-size:clamp(1.05rem,2vw,1.72rem)}
.event{border-left:5px solid var(--asbs-purple);background:#fff;padding:12px 14px;border-radius:12px;margin:7px 0;box-shadow:0 4px 14px rgba(62,30,70,.05)}
.stButton>button,.stDownloadButton>button{min-height:44px;border-radius:11px;font-weight:700;width:100%;border:1px solid #d8cadb;transition:transform .12s ease,box-shadow .12s ease}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 7px 17px rgba(104,0,119,.13)}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,var(--asbs-purple),var(--asbs-magenta));border:0;color:#fff}
input,textarea,[data-baseweb="select"]{font-size:16px!important}
[data-testid="stDataFrame"]{border:1px solid var(--border);border-radius:14px;overflow:hidden;background:#fff}
.stTabs [data-baseweb="tab-list"]{gap:.25rem;overflow-x:auto;overflow-y:hidden;white-space:nowrap;scrollbar-width:thin}
.stTabs [data-baseweb="tab"]{min-height:44px;padding:.55rem .9rem}

/* Medium laptops and tablets */
@media (min-width:769px) and (max-width:1199px){
  [data-testid="stMain"] .block-container{padding:1rem 1.15rem 2.5rem}
  .hero{padding:1.4rem 1.5rem;border-radius:18px}
  [data-testid="stHorizontalBlock"]{gap:.7rem}
  [data-testid="stMetric"]{padding:.7rem .75rem}
  section[data-testid="stSidebar"]{min-width:250px!important}
}

/* Android phones, iPhones and narrow portrait tablets */
@media (max-width:768px){
  [data-testid="stMain"] .block-container{padding:.65rem .72rem 5rem;width:100%;max-width:100%}
  .hero{padding:1.15rem 1rem;border-radius:16px;margin-bottom:.9rem}.hero h1{font-size:1.45rem}.hero p{font-size:.9rem;line-height:1.45}
  .asbs-logo-wrap,.asbs-logo-wrap.center{justify-content:center;padding:.25rem 0 .8rem}
  .asbs-logo{width:min(100%,285px);max-height:none;padding:7px 10px;border-radius:12px}
  [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:column!important;gap:.5rem!important}
  [data-testid="stHorizontalBlock"]>[data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:0!important}
  [data-testid="stForm"]{padding:.25rem;border-radius:14px}
  [data-testid="stMetric"]{padding:.7rem .8rem;margin-bottom:.3rem}
  [data-testid="stMetricValue"]{font-size:1.2rem!important}
  .stButton>button,.stDownloadButton>button{min-height:48px;font-size:.96rem}
  .stTabs [data-baseweb="tab"]{padding:.5rem .72rem;font-size:.82rem}
  [data-testid="stDataFrame"]{max-width:100%;overflow-x:auto}
  section[data-testid="stSidebar"]{width:min(86vw,310px)!important;min-width:min(86vw,310px)!important}
  h1{font-size:1.55rem!important}h2{font-size:1.28rem!important}h3{font-size:1.08rem!important}
}

/* Small phones */
@media (max-width:390px){
  [data-testid="stMain"] .block-container{padding:.5rem .52rem 4.5rem}
  .hero{padding:1rem .85rem}.hero h1{font-size:1.28rem}.hero p{font-size:.84rem}
  .asbs-logo{width:min(100%,250px)}
  .stTabs [data-baseweb="tab"]{padding:.45rem .58rem;font-size:.77rem}
}

/* Landscape phones and compact tablets */
@media (max-height:520px) and (orientation:landscape){
  [data-testid="stMain"] .block-container{padding-top:.45rem}
  .hero{padding:.85rem 1rem}.hero p{margin-top:.25rem}
  .asbs-logo{max-height:62px;width:auto}
}
</style>''',unsafe_allow_html=True)

def render_logo(location='main'):
    if not LOGO.exists():
        st.markdown('<div style="font-weight:800;color:#185a8d;font-size:1.35rem">ASBS & CO</div>', unsafe_allow_html=True)
        return
    encoded = base64.b64encode(LOGO.read_bytes()).decode('ascii')
    position = 'center' if location == 'main' else ''
    variant = 'sidebar' if location == 'sidebar' else ''
    st.markdown(
        f'<div class="asbs-logo-wrap {position}"><img class="asbs-logo {variant}" '
        f'src="data:image/png;base64,{encoded}" alt="ASBS & CO logo"></div>',
        unsafe_allow_html=True,
    )

def client():return create_client(st.secrets['SUPABASE_URL'],st.secrets['SUPABASE_ANON_KEY'])
def safe(v):return re.sub(r'[^A-Za-z0-9_-]+','_',str(v or '').strip()).strip('_') or 'Loan'
def auth_page(sb):
    render_logo('main')
    a,b,c=st.tabs(['Sign in','Create account','Forgot password'])
    with a:
        e=st.text_input('Email',key='le');p=st.text_input('Password',type='password',key='lp')
        if st.button('Sign in',type='primary'):
            try:st.session_state.auth=sb.auth.sign_in_with_password({'email':e,'password':p});st.rerun()
            except Exception as x:st.error(str(x))
    with b:
        e=st.text_input('Email',key='ce');p=st.text_input('Password',type='password',key='cp')
        if st.button('Create account'):
            try:sb.auth.sign_up({'email':e,'password':p});st.success('Account created. Confirm email if enabled, then sign in.')
            except Exception as x:st.error(str(x))
    with c:
        e=st.text_input('Registered email',key='fe')
        if st.button('Send reset email'):
            try:sb.auth.reset_password_email(e,{'redirect_to':'https://asbs-loan.streamlit.app'});st.success('Recovery email sent.')
            except Exception as x:st.error(str(x))
def emi_page():
    st.markdown('<div class="hero"><h1>EMI Calculator</h1><p>Enter any three values. Annual basis fixed at 365 days.</p></div>',unsafe_allow_html=True)
    target=st.selectbox('Calculate',['EMI','Principal','Tenure','ROI'])
    with st.form('ec'):
        a,b=st.columns(2);p=a.number_input('Loan Principal (₹)',0.0,1e12,5451215.0,10000.0,format='%.2f',disabled=target=='Principal');n=b.number_input('Tenure (months)',0,600,45,1,disabled=target=='Tenure')
        a,b=st.columns(2);roi=a.number_input('ROI (% p.a.)',0.0,100.0,8.75,.5,format='%.2f',disabled=target=='ROI');emi=b.number_input('EMI (₹)',0.0,1e12,0.0,1000.0,format='%.2f',disabled=target=='EMI')
        go=st.form_submit_button('Calculate',type='primary',use_container_width=True)
    if go:
        try:st.session_state.emi_result=solve_missing(target,p,int(n),roi,emi)
        except Exception as x:st.error(str(x))
    r=st.session_state.get('emi_result')
    if r:
        m=st.columns(4);m[0].metric('Principal',f"₹{r['principal']:,.2f}");m[1].metric('Tenure',f"{r['tenure']} months");m[2].metric('ROI',f"{r['roi_pct']:.2f}%");m[3].metric('EMI',f"₹{r['emi']:,.2f}")
        if st.button('Use in Repayment Schedule'):st.session_state.schedule_defaults=r;st.session_state.page='Repayment Schedule';st.rerun()
def events():
    t1,t2=st.tabs(['ROI Changes','Part Payments'])
    with t1:
        with st.form('roi',clear_on_submit=True):
            a,b,c=st.columns(3);d=a.date_input('Effective date');r=b.number_input('New ROI (%)',0.0,100.0,10.0,.5,format='%.2f');note=c.text_input('Note')
            if st.form_submit_button('Add ROI change'):st.session_state.roi_events.append({'date':d.isoformat(),'rate':r,'note':note});st.rerun()
        for i,x in enumerate(st.session_state.roi_events):
            a,b=st.columns([8,1]);a.info(f"{x['date']} · {x['rate']:.2f}% · {x.get('note') or 'No note'}")
            if b.button('Remove',key=f'r{i}'):st.session_state.roi_events.pop(i);st.rerun()
    with t2:
        with st.form('pp',clear_on_submit=True):
            a,b,c,d=st.columns(4);day=a.date_input('Payment date');amt=b.number_input('Amount (₹)',.01,step=1000.0,format='%.2f');effect=c.selectbox('Effect',['Reduce Tenure','Reduce EMI']);note=d.text_input('Note')
            if st.form_submit_button('Add part-payment'):st.session_state.pp_events.append({'date':day.isoformat(),'amount':amt,'effect':effect,'note':note});st.rerun()
        for i,x in enumerate(st.session_state.pp_events):
            a,b=st.columns([8,1]);a.info(f"{x['date']} · ₹{x['amount']:,.2f} · {x['effect']} · {x.get('note') or 'No note'}")
            if b.button('Remove',key=f'p{i}'):st.session_state.pp_events.pop(i);st.rerun()
def open_case(case):
    p=case['payload'] if isinstance(case['payload'],dict) else json.loads(case['payload'])
    st.session_state.loaded_case_id=case['id'];st.session_state.loaded_payload=p;st.session_state.roi_events=p.get('roi_events',[]);st.session_state.pp_events=p.get('pp_events',[]);st.session_state.schedule_result=None;st.session_state.page='Repayment Schedule'
def schedule(sb,user):
    d=st.session_state.get('schedule_defaults',{});p0=st.session_state.get('loaded_payload',{})
    st.markdown('<div class="hero"><h1>Repayment Schedule</h1><p>ROI changes and part-payments together. 365-day annual basis.</p></div>',unsafe_allow_html=True)
    a,b,c=st.columns(3);name=a.text_input('Name',p0.get('name',''));acc=b.text_input('Account Number',p0.get('account_number',''));case_name=c.text_input('Case Name',p0.get('case_name','Loan Schedule'))
    a,b,c=st.columns(3);principal=a.number_input('Principal (₹)',1.0,value=float(p0.get('principal',d.get('principal',1_000_000))),step=10000.0,format='%.2f');disb=b.date_input('Disbursement Date',as_date(p0['disbursement']) if p0.get('disbursement') else date.today());first=c.date_input('First EMI Date',as_date(p0['first_emi']) if p0.get('first_emi') else date.today()+timedelta(days=30))
    a,b,c=st.columns(3);tenure=a.number_input('Tenure (months)',1,600,int(p0.get('tenure',d.get('tenure',120))),1);roi=b.number_input('Initial ROI (%)',0.0,100.0,float(p0.get('roi',d.get('roi_pct',10))),.5,format='%.2f');modes=['Recalculate EMI / Keep Tenure','Keep EMI / Reduce Tenure'];mode=c.selectbox('ROI Treatment',modes,index=modes.index(p0.get('roi_treatment',modes[0])) if p0.get('roi_treatment',modes[0]) in modes else 0)
    events()
    if st.button('Calculate / Refresh Schedule',type='primary'):
        try:
            changes=[ROIChange(as_date(x['date']),x['rate']/100,x.get('note','')) for x in st.session_state.roi_events];pps=[Prepayment(as_date(x['date']),x['amount'],x['effect'],x.get('note','')) for x in st.session_state.pp_events]
            rows,ctl=generate_schedule(principal,disb,first,int(tenure),roi/100,changes,pps,mode);pre=pre_emi_interest(principal,disb,first,roi/100);payload={'case_name':case_name,'name':name,'account_number':acc,'principal':rupee(principal),'disbursement':disb.isoformat(),'first_emi':first.isoformat(),'tenure':int(tenure),'roi':roi,'roi_treatment':mode,'roi_events':st.session_state.roi_events,'pp_events':st.session_state.pp_events};st.session_state.schedule_result=(rows,ctl,pre,payload)
        except Exception as x:st.error(str(x))
    if not st.session_state.get('schedule_result'):return
    rows,ctl,pre,payload=st.session_state.schedule_result
    m=st.columns(7);vals=[('Initial EMI',ctl['initial_emi']),('Interest',ctl['total_interest']),('Part Payments',ctl['total_prepayment']),('Variance',ctl['principal_variance']),('Schedule Rows',ctl['schedule_rows']),('Payoff',ctl['payoff_date'].strftime('%d-%m-%Y')),('Control',ctl['status'])]
    for col,(k,v) in zip(m,vals):col.metric(k,f"₹{v:,.2f}" if isinstance(v,float) else str(v))
    df=pd.DataFrame([{'EMI #':r.emi_no,'Due Date':r.due_date,'Opening Principal':r.opening_principal,'ROI (% p.a.)':r.roi*100,'Interest Component':r.interest_component,'Principal Component':r.principal_component,'EMI':r.emi,'Part Prepayment':r.part_prepayment,'Closing Principal':r.closing_principal} for r in rows])
    money_cols=['Opening Principal','Interest Component','Principal Component','EMI','Part Prepayment','Closing Principal'];cfg={x:st.column_config.NumberColumn(format='₹ %.2f') for x in money_cols};cfg['ROI (% p.a.)']=st.column_config.NumberColumn(format='%.2f')
    st.dataframe(df,use_container_width=True,hide_index=True,column_config=cfg)
    pdf=build_pdf(LOGO,payload,pre,ctl,rows);xlsx=build_excel(payload,pre,ctl,rows,st.session_state.roi_events,st.session_state.pp_events);base=f"ASBS_RPS_{safe(acc)}";buttons=st.columns(3);buttons[0].download_button('Download PDF',pdf,f'{base}.pdf','application/pdf');buttons[1].download_button('Download Excel',xlsx,f'{base}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    if buttons[2].button('Save Case'):
        record={'user_id':user.id,'case_name':case_name,'borrower':name,'loan_reference':acc,'payload':payload}
        try:
            if st.session_state.get('loaded_case_id'):sb.table('loan_cases').update(record).eq('id',st.session_state.loaded_case_id).execute()
            else:
                response=sb.table('loan_cases').insert(record).execute()
                if response.data:st.session_state.loaded_case_id=response.data[0]['id']
            st.success('Case saved. Search by account number in Saved Cases.')
        except Exception as x:st.error(f'Save failed: {x}')
def saved(sb,user):
    st.header('Saved Cases');q=st.text_input('Search by Account Number or Name',placeholder='Type account number or name')
    try:cases=sb.table('loan_cases').select('*').eq('user_id',user.id).order('updated_at',desc=True).execute().data
    except Exception as x:st.error(str(x));return
    query=q.strip().lower()
    if query:cases=[x for x in cases if query in str(x.get('loan_reference','')).lower() or query in str(x.get('borrower','')).lower() or query in str(x.get('case_name','')).lower()]
    st.caption(f'{len(cases)} case(s) found')
    for case in cases:
        a,b,c=st.columns([5,1,1]);a.markdown(f"**Account: {case.get('loan_reference') or '-'}**  \nName: {case.get('borrower') or '-'} · {case.get('case_name') or '-'}")
        if b.button('Open / Edit',key=f"o{case['id']}"):open_case(case);st.rerun()
        if c.button('Delete',key=f"d{case['id']}"):sb.table('loan_cases').delete().eq('id',case['id']).execute();st.rerun()
def main(sb):
    for k,v in [('page','EMI Calculator'),('roi_events',[]),('pp_events',[])]:st.session_state.setdefault(k,v)
    user=st.session_state.auth.user
    with st.sidebar:
        render_logo('sidebar')
        pages=['EMI Calculator','Repayment Schedule','Saved Cases','Profile'];st.session_state.page=st.radio('Workspace',pages,index=pages.index(st.session_state.page));st.caption(user.email)
        if st.button('Sign out'):sb.auth.sign_out();st.session_state.clear();st.rerun()
    {'EMI Calculator':lambda:emi_page(),'Repayment Schedule':lambda:schedule(sb,user),'Saved Cases':lambda:saved(sb,user),'Profile':lambda:st.write(user.email)}[st.session_state.page]()
sb=client()
if 'auth' in st.session_state:
    try:
        s=st.session_state.auth.session;restored=sb.auth.set_session(s.access_token,s.refresh_token)
        if restored and restored.session:st.session_state.auth=restored
    except Exception:st.session_state.pop('auth',None);st.rerun()
if 'auth' not in st.session_state:auth_page(sb)
else:main(sb)
