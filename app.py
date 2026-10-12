from pathlib import Path
from datetime import date,timedelta
import json,sqlite3,hashlib,secrets,os
import pandas as pd
import streamlit as st
from loan_engine import *
from pdf_report import build
from excel_export import build_excel
ROOT=Path(__file__).parent;LOGO=ROOT/'assets/asbs-logo.png';DB=ROOT/'data/asbs.db'
def con():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 with con() as c:c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,pwd TEXT);CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,user_id INTEGER,name TEXT,payload TEXT,pdf BLOB,xlsx BLOB,updated TEXT DEFAULT CURRENT_TIMESTAMP);')
def hp(x):return hashlib.sha256(x.encode()).hexdigest()
init();st.set_page_config(page_title='ASBS Loan Studio V3',page_icon='🏦',layout='wide')
st.markdown('''<style>.stApp{background:#faf7fb}.block-container{max-width:1450px}.hero{background:linear-gradient(120deg,#580064,#9700a5);color:white;padding:22px;border-radius:18px;margin-bottom:15px}.hero h1{color:white}.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:700}section[data-testid=stSidebar]{background:#690078}section[data-testid=stSidebar] *{color:white}@media(max-width:768px){div[data-testid=column]{width:100%!important;flex:1 1 100%!important}.block-container{padding:.7rem}}</style>''',unsafe_allow_html=True)
def login():
 st.image(str(LOGO),width=280);a,b=st.tabs(['Sign in','Create account'])
 with a:
  e=st.text_input('Email');p=st.text_input('Password',type='password')
  if st.button('Sign in',type='primary'):
   with con() as c:r=c.execute('SELECT * FROM users WHERE email=? AND pwd=?',(e.lower(),hp(p))).fetchone()
   if r:st.session_state.user=dict(r);st.rerun()
   else:st.error('Invalid login.')
 with b:
  n=st.text_input('Name');e=st.text_input('Email',key='ce');p=st.text_input('Password',type='password',key='cp')
  if st.button('Create'):
   try:
    with con() as c:c.execute('INSERT INTO users(name,email,pwd) VALUES(?,?,?)',(n,e.lower(),hp(p)))
    st.success('Created. Sign in.')
   except Exception as x:st.error(str(x))
def main():
 for k,v in [('roi',[]),('pp',[]),('result',None)]:st.session_state.setdefault(k,v)
 with st.sidebar:
  st.image(str(LOGO),use_container_width=True);page=st.radio('Workspace',['Calculator','Saved Cases']);st.caption(st.session_state.user['email'])
  if st.button('Sign out'):st.session_state.clear();st.rerun()
 if page=='Saved Cases':
  st.header('Saved Cases')
  with con() as c:items=c.execute('SELECT * FROM cases WHERE user_id=? ORDER BY updated DESC',(st.session_state.user['id'],)).fetchall()
  for x in items:
   p=json.loads(x['payload']);a,b,c=st.columns([5,1,1]);a.write(f"**{x['name']}** · {p['borrower']} · {x['updated']}")
   if b.button('Edit',key=f"e{x['id']}"):st.session_state.loaded=p;st.session_state.roi=p['roi_events'];st.session_state.pp=p['pp_events'];st.session_state.edit=x['id'];st.rerun()
   c.download_button('Excel',x['xlsx'],f"{x['name']}.xlsx",key=f"x{x['id']}");st.download_button('PDF',x['pdf'],f"{x['name']}.pdf",key=f"p{x['id']}")
  return
 L=st.session_state.get('loaded',{});st.markdown('<div class="hero"><h1>ASBS Loan Repayment Planner</h1><p>Chronological, auditable and export-ready schedule.</p></div>',unsafe_allow_html=True)
 c1,c2,c3=st.columns(3);borrower=c1.text_input('Borrower',L.get('borrower',''));ref=c2.text_input('Reference',L.get('ref',''));name=c3.text_input('Case name',L.get('name','Loan Schedule'))
 c1,c2,c3=st.columns(3);principal=c1.number_input('Principal (₹)',1.0,value=float(L.get('principal',1000000)));disb=c2.date_input('Disbursement',as_date(L.get('disb')) or date.today());first=c3.date_input('First EMI',as_date(L.get('first')) or date.today()+timedelta(days=30))
 c1,c2,c3,c4=st.columns(4);tenure=c1.number_input('Tenure',1,600,int(L.get('tenure',120)));roi=c2.number_input('Initial ROI %',0.0,100.0,float(L.get('rate',10)),.01);mode=c3.selectbox('ROI treatment',['Keep EMI / Reduce tenure','Recalculate EMI']);basis=c4.selectbox('Interest basis',[360,365])
 t1,t2=st.tabs(['ROI Changes','Part Payments'])
 with t1:
  with st.form('r',clear_on_submit=True):
   a,b,c=st.columns(3);d=a.date_input('Effective date');rr=b.number_input('New ROI %',0.0,100.0,10.0,.01);n=c.text_input('Note')
   if st.form_submit_button('Add ROI change'):st.session_state.roi.append({'date':d.isoformat(),'rate':rr,'note':n});st.rerun()
  for i,x in enumerate(st.session_state.roi):
   a,b=st.columns([8,1]);a.info(f"{x['date']} | {x['rate']:.3f}% | {x['note'] or 'No note'}")
   if b.button('Remove',key=f'r{i}'):st.session_state.roi.pop(i);st.rerun()
 with t2:
  with st.form('p',clear_on_submit=True):
   a,b,c,d=st.columns(4);dd=a.date_input('Payment date');amt=b.number_input('Amount ₹',0.01);eff=c.selectbox('Effect',['Reduce Tenure','Reduce EMI']);note=d.text_input('Note')
   if st.form_submit_button('Add part-payment'):st.session_state.pp.append({'date':dd.isoformat(),'amount':amt,'effect':eff,'note':note});st.rerun()
  for i,x in enumerate(st.session_state.pp):
   a,b=st.columns([8,1]);a.info(f"{x['date']} | ₹{x['amount']:,.2f} | {x['effect']} | {x['note'] or 'No note'}")
   if b.button('Remove',key=f'p{i}'):st.session_state.pp.pop(i);st.rerun()
 if st.button('Calculate / Refresh',type='primary',use_container_width=True):
  try:
   rc=[ROIChange(as_date(x['date']),x['rate']/100,x['note']) for x in st.session_state.roi];pp=[Prepayment(as_date(x['date']),x['amount'],x['effect'],x['note']) for x in st.session_state.pp]
   rows,ctl=generate(principal,disb,first,int(tenure),roi/100,rc,pp,mode,basis);pre=pre_emi(principal,disb,first,roi/100,basis);payload={'name':name,'borrower':borrower,'ref':ref,'principal':principal,'disb':disb.isoformat(),'first':first.isoformat(),'tenure':tenure,'rate':roi,'roi_events':st.session_state.roi,'pp_events':st.session_state.pp};st.session_state.result=(rows,ctl,pre,payload)
  except Exception as x:st.error(str(x))
 if st.session_state.result:
  rows,ctl,pre,payload=st.session_state.result
  cs=st.columns(6)
  for c,(k,v) in zip(cs,[('Initial EMI',ctl['initial_emi']),('Total Interest',ctl['total_interest']),('Part Payments',ctl['total_prepayment']),('Principal Variance',ctl['principal_variance']),('Payoff',ctl['payoff_date'].strftime('%d-%m-%Y')),('Control',ctl['status'])]):c.metric(k,f'₹{v:,.2f}' if isinstance(v,(int,float)) else v)
  df=pd.DataFrame([{'EMI #':r.emi_no,'Due Date':r.due_date,'Opening Principal':r.opening_principal,'ROI (% p.a.)':r.roi*100,'Interest Component':r.interest_component,'Principal Component':r.principal_component,'EMI':r.emi,'Part Prepayment':r.part_prepayment,'Closing Principal':r.closing_principal} for r in rows]).sort_values('EMI #').reset_index(drop=True)
  st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "EMI #": st.column_config.NumberColumn(
            "EMI #",
            format="%d"
        ),
        "Due Date": st.column_config.DateColumn(
            "Due Date",
            format="DD-MM-YYYY"
        ),
        "Opening Principal": st.column_config.NumberColumn(
            "Opening Principal",
            format="₹ %.2f"
        ),
        "ROI (% p.a.)": st.column_config.NumberColumn(
            "ROI (% p.a.)",
            format="%.3f%%"
        ),
        "Interest Component": st.column_config.NumberColumn(
            "Interest Component",
            format="₹ %.2f"
        ),
        "Principal Component": st.column_config.NumberColumn(
            "Principal Component",
            format="₹ %.2f"
        ),
        "EMI": st.column_config.NumberColumn(
            "EMI",
            format="₹ %.2f"
        ),
        "Part Prepayment": st.column_config.NumberColumn(
            "Part Prepayment",
            format="₹ %.2f"
        ),
        "Closing Principal": st.column_config.NumberColumn(
            "Closing Principal",
            format="₹ %.2f"
        ),
    },
)
  pdf=build(LOGO,borrower,ref,principal,pre,ctl,rows);xlsx=build_excel(payload,pre,ctl,rows,st.session_state.roi,st.session_state.pp);a,b,c=st.columns(3);a.download_button('Download PDF',pdf,f'{name}.pdf','application/pdf',use_container_width=True);b.download_button('Download Excel',xlsx,f'{name}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
  if c.button('Save Case',use_container_width=True):
   with con() as db:
    if st.session_state.get('edit'):db.execute('UPDATE cases SET name=?,payload=?,pdf=?,xlsx=?,updated=CURRENT_TIMESTAMP WHERE id=?',(name,json.dumps(payload),pdf,xlsx,st.session_state.edit))
    else:db.execute('INSERT INTO cases(user_id,name,payload,pdf,xlsx) VALUES(?,?,?,?,?)',(st.session_state.user['id'],name,json.dumps(payload),pdf,xlsx))
   st.success('Case, PDF and Excel saved.')
if 'user' not in st.session_state:login()
else:main()
