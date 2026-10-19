from pathlib import Path
from datetime import date,timedelta
import json
import pandas as pd
import streamlit as st
from supabase import create_client
from finance_engine import *
from exports import pdf_bytes,excel_bytes
ROOT=Path(__file__).resolve().parent;LOGO=ROOT/'assets/asbs-logo.png'
st.set_page_config(page_title='ASBS Loan Studio',page_icon='🏦',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>:root{--p:#680077;--p2:#9b00ab}.stApp{background:#faf7fb}.block-container{max-width:1400px;padding-top:1rem}.hero{background:linear-gradient(120deg,var(--p),var(--p2));color:white;padding:22px;border-radius:18px;margin-bottom:16px}.hero h1{color:white;margin:0}.event{border-left:5px solid var(--p);background:white;padding:12px;border-radius:12px;margin:6px 0}.stButton>button,.stDownloadButton>button{min-height:44px;border-radius:10px;font-weight:700;width:100%}section[data-testid=stSidebar]{background:#f2f3f7}@media(max-width:768px){.block-container{padding:.55rem}.hero{padding:15px}.hero h1{font-size:1.4rem}div[data-testid=column]{width:100%!important;flex:1 1 100%!important}.desktop-table{display:none}.stTabs [data-baseweb=tab]{padding:8px;font-size:.82rem}div[data-testid=stMetric]{background:white;border-radius:12px;padding:8px}}</style>''',unsafe_allow_html=True)
def sb():return create_client(st.secrets['SUPABASE_URL'],st.secrets['SUPABASE_ANON_KEY'])
def auth_page(client):
    if LOGO.exists():st.image(LOGO.read_bytes(),width=260)
    st.markdown('<div class="hero"><h1>ASBS Loan Studio</h1><p>EMI calculator, repayment schedules, ROI changes, part-payments and exports.</p></div>',unsafe_allow_html=True)
    a,b,c=st.tabs(['Sign in','Create account','Forgot password'])
    with a:
        e=st.text_input('Email',key='le');p=st.text_input('Password',type='password',key='lp')
        if st.button('Sign in',type='primary'):
            try:st.session_state.auth=client.auth.sign_in_with_password({'email':e,'password':p});st.rerun()
            except Exception as x:st.error(str(x))
    with b:
        e=st.text_input('Email',key='ce');p=st.text_input('Password',type='password',key='cp')
        if st.button('Create account'):
            try:client.auth.sign_up({'email':e,'password':p});st.success('Account created. Confirm the email if enabled, then sign in.')
            except Exception as x:st.error(str(x))
    with c:
        e=st.text_input('Registered email',key='fe')
        if st.button('Send reset email'):
            try:client.auth.reset_password_email(e,{'redirect_to':'https://asbs-loan.streamlit.app'});st.success('Recovery email sent.')
            except Exception as x:st.error(str(x))
def emi_page():
    st.markdown('<div class="hero"><h1>EMI Calculator</h1><p>Enter any three values. Annual basis is fixed at 365 days.</p></div>',unsafe_allow_html=True)
    target=st.selectbox('Calculate',['EMI','Principal','Tenure','ROI'])
    with st.form('ec'):
        a,b=st.columns(2);p=a.number_input('Loan Principal (₹)',0.0,5451215.0,10000.0,disabled=target=='Principal');n=b.number_input('Tenure (months)',0,600,45,1,disabled=target=='Tenure')
        a,b=st.columns(2);roi=a.number_input('ROI (% p.a.)',0.0,100.0,8.75,.01,disabled=target=='ROI');emi=b.number_input('EMI (₹)',0.0,0.0,1000.0,disabled=target=='EMI');st.caption('Regular basis: 30 days | Annual basis: 365 days only')
        go=st.form_submit_button('Calculate',type='primary',use_container_width=True)
    if go:
        try:st.session_state.emi_result=solve_missing(target,p,int(n),roi,emi)
        except Exception as x:st.error(str(x))
    if st.session_state.get('emi_result'):
        r=st.session_state.emi_result;m=st.columns(4);m[0].metric('Principal',f"₹{r['principal']:,.2f}");m[1].metric('Tenure',f"{r['tenure']} months");m[2].metric('ROI',f"{r['roi_pct']:.4f}%");m[3].metric('EMI',f"₹{r['emi']:,.2f}");st.success(f"Calculation Control: {r['control']} | Reverse variance ₹{r['variance']:.4f}")
        if st.button('Use in Repayment Schedule'):st.session_state.schedule_defaults=r;st.session_state.page='Repayment Schedule';st.rerun()
def events_ui():
    t1,t2=st.tabs(['ROI Changes','Part Payments'])
    with t1:
        with st.form('roi_add',clear_on_submit=True):
            a,b,c=st.columns(3);d=a.date_input('Effective date');r=b.number_input('New ROI %',0.0,100.0,10.0,.01);note=c.text_input('Note')
            if st.form_submit_button('Add ROI change'):st.session_state.roi_events.append({'date':d.isoformat(),'rate':r,'note':note});st.rerun()
        for i,x in enumerate(st.session_state.roi_events):
            a,b=st.columns([8,1]);a.markdown(f"<div class='event'><b>{x['date']}</b> · {x['rate']:.3f}% · {x['note'] or 'No note'}</div>",unsafe_allow_html=True)
            if b.button('Remove',key=f'r{i}'):st.session_state.roi_events.pop(i);st.rerun()
    with t2:
        with st.form('pp_add',clear_on_submit=True):
            a,b,c,d=st.columns(4);day=a.date_input('Payment date');amount=b.number_input('Amount (₹)',.01,step=1000.0);effect=c.selectbox('Effect',['Reduce Tenure','Reduce EMI']);note=d.text_input('Note')
            if st.form_submit_button('Add part-payment'):st.session_state.pp_events.append({'date':day.isoformat(),'amount':amount,'effect':effect,'note':note});st.rerun()
        for i,x in enumerate(st.session_state.pp_events):
            a,b=st.columns([8,1]);a.markdown(f"<div class='event'><b>{x['date']}</b> · ₹{x['amount']:,.2f} · {x['effect']} · {x['note'] or 'No note'}</div>",unsafe_allow_html=True)
            if b.button('Remove',key=f'p{i}'):st.session_state.pp_events.pop(i);st.rerun()
def schedule_page(client,user):
    d=st.session_state.get('schedule_defaults',{});st.markdown('<div class="hero"><h1>Repayment Schedule</h1><p>ROI changes and part-payments work together in chronological order.</p></div>',unsafe_allow_html=True)
    a,b,c=st.columns(3);borrower=a.text_input('Borrower');ref=b.text_input('Loan / Case reference');name=c.text_input('Case name','Loan Schedule')
    a,b,c=st.columns(3);p=a.number_input('Principal (₹)',1.0,value=float(d.get('principal',1000000)));disb=b.date_input('Disbursement date',date.today());first=c.date_input('First EMI date',date.today()+timedelta(days=30))
    a,b,c=st.columns(3);n=a.number_input('Tenure (months)',1,600,int(d.get('tenure',120)));roi=b.number_input('Initial ROI (%)',0.0,100.0,float(d.get('roi_pct',10)),.01);mode=c.selectbox('ROI treatment',['Keep EMI / Reduce tenure','Recalculate EMI']);st.caption('Annual basis fixed at 365 days')
    events_ui()
    if st.button('Calculate / Refresh Schedule',type='primary'):
        try:
            rc=[ROIChange(as_date(x['date']),x['rate']/100,x['note']) for x in st.session_state.roi_events];pp=[Prepayment(as_date(x['date']),x['amount'],x['effect'],x['note']) for x in st.session_state.pp_events]
            rows,ctl=generate_schedule(p,disb,first,int(n),roi/100,rc,pp,mode);pre=pre_emi(p,disb,first,roi/100);payload={'case_name':name,'borrower':borrower,'ref':ref,'principal':p,'disb':disb.isoformat(),'first':first.isoformat(),'tenure':int(n),'roi':roi,'mode':mode,'roi_events':st.session_state.roi_events,'pp_events':st.session_state.pp_events};st.session_state.schedule_result=(rows,ctl,pre,payload)
        except Exception as x:st.error(str(x))
    if st.session_state.get('schedule_result'):
        rows,ctl,pre,payload=st.session_state.schedule_result;m=st.columns(6)
        values=[('Initial EMI',f"₹{ctl['initial_emi']:,.2f}"),('Interest',f"₹{ctl['total_interest']:,.2f}"),('Part Payments',f"₹{ctl['total_prepayment']:,.2f}"),('Variance',f"₹{ctl['principal_variance']:,.2f}"),('Payoff',ctl['payoff_date'].strftime('%d-%m-%Y')),('Control',ctl['status'])]
        for col,(k,v) in zip(m,values):col.metric(k,v)
        data=[{'EMI #':r.emi_no,'Due Date':r.due_date,'Opening Principal':r.opening_principal,'ROI (% p.a.)':r.roi*100,'Interest Component':r.interest_component,'Principal Component':r.principal_component,'EMI':r.emi,'Part Prepayment':r.part_prepayment,'Closing Principal':r.closing_principal} for r in rows];df=pd.DataFrame(data);st.dataframe(df,use_container_width=True,hide_index=True)
        with st.expander('Mobile compact schedule'):
            for r in rows:st.markdown(f"<div class='event'><b>EMI #{r.emi_no} · {r.due_date:%d-%m-%Y}</b><br>EMI ₹{r.emi:,.2f} · Interest ₹{r.interest_component:,.2f}<br>Principal ₹{r.principal_component:,.2f} · PP ₹{r.part_prepayment:,.2f}<br>Closing ₹{r.closing_principal:,.2f}</div>",unsafe_allow_html=True)
        pdf=pdf_bytes(LOGO,payload,pre,ctl,rows);xlsx=excel_bytes(payload,pre,ctl,rows,st.session_state.roi_events,st.session_state.pp_events);a,b,c=st.columns(3);a.download_button('Download PDF',pdf,f'{name}.pdf','application/pdf');b.download_button('Download Excel',xlsx,f'{name}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        if c.button('Save Case'):
            record={'user_id':user.id,'case_name':name,'borrower':borrower,'loan_reference':ref,'payload':payload}
            try:client.table('loan_cases').insert(record).execute();st.success('Saved online. It will appear on every device.')
            except Exception as x:st.error(f'Save failed. Run setup.sql in Supabase first. {x}')
def saved_page(client,user):
    st.header('Saved Cases')
    try:items=client.table('loan_cases').select('*').eq('user_id',user.id).order('updated_at',desc=True).execute().data
    except Exception as x:st.error(f'Cannot load cases. Run setup.sql. {x}');return
    for x in items:
        with st.container(border=True):st.subheader(x['case_name']);st.write(f"{x.get('borrower') or '-'} · {x.get('loan_reference') or '-'}");st.caption(x.get('updated_at',''))
def main(client):
    for k,v in [('page','EMI Calculator'),('roi_events',[]),('pp_events',[])]:st.session_state.setdefault(k,v)
    user=st.session_state.auth.user
    with st.sidebar:
        if LOGO.exists():st.image(LOGO.read_bytes(),use_container_width=True)
        pages=['EMI Calculator','Repayment Schedule','Saved Cases','Profile'];st.session_state.page=st.radio('Workspace',pages,index=pages.index(st.session_state.page));st.caption(user.email)
        if st.button('Sign out'):client.auth.sign_out();st.session_state.clear();st.rerun()
    if st.session_state.page=='EMI Calculator':emi_page()
    elif st.session_state.page=='Repayment Schedule':schedule_page(client,user)
    elif st.session_state.page=='Saved Cases':saved_page(client,user)
    else:st.header('Profile');st.write(user.email);st.caption('Supabase account works across devices.')
client=sb()
if 'auth' not in st.session_state:auth_page(client)
else:main(client)
