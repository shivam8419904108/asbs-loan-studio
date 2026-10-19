from pathlib import Path
import os
import streamlit as st
from finance_engine import solve_missing

ROOT=Path(__file__).resolve().parent
LOGO=ROOT/'asbs-logo.png'
st.set_page_config(page_title='ASBS Loan Studio',page_icon='🏦',layout='wide',initial_sidebar_state='collapsed')

st.markdown('''<style>
:root{--p:#690078;--p2:#9700a5}.stApp{background:#faf7fb}.block-container{max-width:1180px;padding-top:1rem}.hero{background:linear-gradient(120deg,var(--p),var(--p2));color:white;padding:22px;border-radius:18px;margin-bottom:16px}.hero h1{color:white;margin:0}.hero p{margin:6px 0 0}.result{background:white;border:1px solid #eadfec;border-left:6px solid var(--p);padding:18px;border-radius:16px}.stButton>button{min-height:46px;border-radius:11px;font-weight:700;width:100%}
@media(max-width:768px){.block-container{padding:.55rem}.hero{padding:16px}.hero h1{font-size:1.35rem}div[data-testid="column"]{width:100%!important;flex:1 1 100%!important}.stTabs [data-baseweb="tab-list"]{gap:3px}.stTabs [data-baseweb="tab"]{padding:8px 9px;font-size:.83rem}div[data-testid="stMetric"]{background:white;border-radius:12px;padding:9px}.stDataFrame{font-size:.78rem}}
</style>''',unsafe_allow_html=True)

def require_supabase():
    try:
        from supabase import create_client
        url=st.secrets['SUPABASE_URL']; key=st.secrets['SUPABASE_ANON_KEY']
        return create_client(url,key)
    except Exception:
        return None

def auth_screen(sb):
    if LOGO.exists(): st.image(LOGO.read_bytes(),width=260)
    st.markdown('<div class="hero"><h1>ASBS Loan Studio</h1><p>365-day loan calculations, schedules and saved cases.</p></div>',unsafe_allow_html=True)
    if sb is None:
        st.error('Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Secrets.');st.stop()
    sign,create,forgot=st.tabs(['Sign in','Create account','Forgot password'])
    with sign:
        e=st.text_input('Email',key='se');p=st.text_input('Password',type='password',key='sp')
        if st.button('Sign in',type='primary'):
            try: st.session_state.auth=sb.auth.sign_in_with_password({'email':e,'password':p});st.rerun()
            except Exception as x: st.error(f'Sign in failed: {x}')
    with create:
        e=st.text_input('Email',key='ce');p=st.text_input('Password',type='password',key='cp')
        if st.button('Create account'):
            try: sb.auth.sign_up({'email':e,'password':p});st.success('Account created. Check email if confirmation is enabled, then sign in.')
            except Exception as x: st.error(f'Account creation failed: {x}')
    with forgot:
        e=st.text_input('Registered email',key='fe')
        if st.button('Send reset email'):
            try: sb.auth.reset_password_email(e);st.success('Password reset email sent.')
            except Exception as x: st.error(f'Reset failed: {x}')

def emi_calculator():
    st.markdown('<div class="hero"><h1>EMI Calculator</h1><p>Enter any three values. The fourth value is calculated using a fixed 30/365 method.</p></div>',unsafe_allow_html=True)
    target=st.selectbox('What do you want to calculate?',['EMI','Principal','Tenure','ROI'])
    with st.form('emi_calc'):
        c1,c2=st.columns(2)
        principal=c1.number_input('Loan Principal (₹)',min_value=0.0,value=5451215.0,step=10000.0,disabled=target=='Principal')
        tenure=c2.number_input('Tenure (months)',min_value=0,value=45,step=1,disabled=target=='Tenure')
        c3,c4=st.columns(2)
        roi=c3.number_input('ROI (% p.a.)',min_value=0.0,max_value=100.0,value=8.75,step=.01,disabled=target=='ROI')
        emi=c4.number_input('EMI (₹)',min_value=0.0,value=0.0,step=1000.0,disabled=target=='EMI')
        st.caption('Regular EMI basis: 30 days | Annual basis: 365 days only')
        go=st.form_submit_button('Calculate',type='primary',use_container_width=True)
    if go:
        try: st.session_state.emi_result=solve_missing(target,principal,int(tenure),roi,emi)
        except Exception as x: st.error(str(x))
    r=st.session_state.get('emi_result')
    if r:
        st.markdown('<div class="result">',unsafe_allow_html=True)
        m=st.columns(4);m[0].metric('Principal',f"₹{r['principal']:,.2f}");m[1].metric('Tenure',f"{r['tenure']} months");m[2].metric('ROI',f"{r['roi_pct']:.4f}%");m[3].metric('EMI',f"₹{r['emi']:,.2f}")
        st.success(f"Calculation Control: {r['control']} | Reverse EMI variance: ₹{r['variance']:.4f}")
        if st.button('Use these values in Repayment Schedule'):
            st.session_state.schedule_defaults=r;st.session_state.page='Repayment Schedule';st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)

def placeholder_schedule():
    st.header('Repayment Schedule')
    d=st.session_state.get('schedule_defaults')
    if d: st.info(f"Loaded from EMI Calculator: Principal ₹{d['principal']:,.2f}, {d['tenure']} months, ROI {d['roi_pct']:.4f}%, EMI ₹{d['emi']:,.2f}")
    st.warning('Copy your existing ROI-change, part-payment, PDF and Excel schedule section below this page. Change every annual basis to 365 and remove every 360 selector.')

def main(sb):
    st.session_state.setdefault('page','EMI Calculator')
    user_id=st.session_state.auth.user.id
    with st.sidebar:
        if LOGO.exists():st.image(LOGO.read_bytes(),use_container_width=True)
        pages=['EMI Calculator','Repayment Schedule','Saved Cases','Profile']
        st.session_state.page=st.radio('Workspace',pages,index=pages.index(st.session_state.page))
        st.caption(st.session_state.auth.user.email)
        if st.button('Sign out'):sb.auth.sign_out();st.session_state.clear();st.rerun()
    if st.session_state.page=='EMI Calculator':emi_calculator()
    elif st.session_state.page=='Repayment Schedule':placeholder_schedule()
    elif st.session_state.page=='Saved Cases':st.header('Saved Cases');st.info('Saved cases must be loaded from Supabase using the signed-in user ID: '+user_id)
    else:st.header('Profile');st.write(st.session_state.auth.user.email);st.caption('Accounts are stored in Supabase and work across phones and laptops.')

sb=require_supabase()
if 'auth' not in st.session_state:auth_screen(sb)
else:main(sb)
