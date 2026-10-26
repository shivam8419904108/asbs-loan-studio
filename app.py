from pathlib import Path
from datetime import date, timedelta
import base64
import json
import re

import pandas as pd
import streamlit as st
from supabase import create_client

from finance_engine import (
    ROIChange,
    Prepayment,
    as_date,
    generate_schedule,
    pre_emi_interest,
    rupee,
    solve_missing,
)
from exports import build_pdf, build_excel

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "assets" / "asbs-logo.png"

st.set_page_config(
    page_title="ASBS Loan Studio",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
:root{--p:#680077;--p2:#9b00ab;--border:#e7dce9;--text:#231426}
.stApp{background:linear-gradient(145deg,#fbf9fc 0%,#f4eef7 100%)}
[data-testid="stMain"] .block-container{width:min(100%,1440px);max-width:1440px;padding:1.2rem 2rem 3rem;margin:0 auto}
.hero{background:linear-gradient(125deg,var(--p),var(--p2));color:#fff;padding:1.65rem 1.9rem;border-radius:22px;margin:0 0 1.2rem;box-shadow:0 16px 36px rgba(104,0,119,.16)}
.hero h1{color:#fff;margin:0;font-size:clamp(1.55rem,3vw,2.35rem)}
.hero p{margin:.65rem 0 0;font-size:clamp(.92rem,1.4vw,1.06rem)}
.asbs-logo-wrap{display:flex;justify-content:center;width:100%;padding:.35rem 0 1rem;overflow:visible}
.asbs-logo{display:block;width:auto;max-width:min(100%,330px);height:auto;max-height:105px;object-fit:contain;background:#fff;border-radius:14px;padding:8px 12px;box-sizing:border-box;box-shadow:0 6px 18px rgba(40,20,45,.08)}
.asbs-logo.sidebar{max-width:100%;max-height:82px;padding:6px 8px}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#fff 0%,#f5eff7 100%);border-right:1px solid var(--border)}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--border);border-radius:15px;padding:.8rem .9rem}
.stButton>button,.stDownloadButton>button{min-height:44px;border-radius:11px;font-weight:700;width:100%}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,var(--p),var(--p2));border:0;color:#fff}
input,textarea,[data-baseweb="select"]{font-size:16px!important}
[data-testid="stDataFrame"]{border:1px solid var(--border);border-radius:14px;overflow:hidden;background:#fff}
@media (min-width:769px) and (max-width:1199px){[data-testid="stMain"] .block-container{padding:1rem 1.15rem 2.5rem}}
@media (max-width:768px){
 [data-testid="stMain"] .block-container{padding:.65rem .72rem 5rem;width:100%;max-width:100%}
 .hero{padding:1.1rem 1rem;border-radius:16px}.hero h1{font-size:1.42rem}.hero p{font-size:.88rem}
 .asbs-logo{width:min(100%,285px);max-height:none}
 [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:column!important;gap:.5rem!important}
 [data-testid="stHorizontalBlock"]>[data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:0!important}
 .stButton>button,.stDownloadButton>button{min-height:48px}
 [data-testid="stDataFrame"]{max-width:100%;overflow-x:auto}
 section[data-testid="stSidebar"]{width:min(86vw,310px)!important;min-width:min(86vw,310px)!important}
}
</style>
""",
    unsafe_allow_html=True,
)

PAGES = ["EMI Calculator", "Repayment Schedule", "Saved Cases", "Profile"]
SCHEDULE_WIDGET_KEYS = [
    "schedule_name", "schedule_account", "schedule_case_name",
    "schedule_principal", "schedule_disbursement", "schedule_first_emi",
    "schedule_tenure", "schedule_roi", "schedule_mode",
]


def supabase_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])


def render_logo(sidebar=False):
    if not LOGO.exists():
        st.markdown("### ASBS & CO")
        return
    encoded = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    css_class = "asbs-logo sidebar" if sidebar else "asbs-logo"
    st.markdown(
        f'<div class="asbs-logo-wrap"><img class="{css_class}" '
        f'src="data:image/png;base64,{encoded}" alt="ASBS & CO logo"></div>',
        unsafe_allow_html=True,
    )


def safe_filename(value):
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return cleaned or "Loan"


def normalize_payload(case):
    payload = case.get("payload") or {}
    if not isinstance(payload, dict):
        payload = json.loads(payload)
    payload = dict(payload)
    payload.setdefault("name", payload.get("borrower", case.get("borrower", "")))
    payload.setdefault("account_number", payload.get("ref", case.get("loan_reference", "")))
    payload.setdefault("case_name", case.get("case_name", payload.get("case_name", "Loan Schedule")))
    payload.setdefault("roi_events", [])
    payload.setdefault("pp_events", [])
    payload.setdefault("roi_treatment", "Recalculate EMI / Keep Tenure")
    return payload


def calculation_from_payload(payload):
    changes = [
        ROIChange(as_date(item["date"]), float(item["rate"]) / 100, item.get("note", ""))
        for item in payload.get("roi_events", [])
    ]
    payments = [
        Prepayment(
            as_date(item["date"]), float(item["amount"]),
            item["effect"], item.get("note", ""),
        )
        for item in payload.get("pp_events", [])
    ]
    rows, controls = generate_schedule(
        float(payload["principal"]),
        as_date(payload["disbursement"]),
        as_date(payload["first_emi"]),
        int(payload["tenure"]),
        float(payload["roi"]) / 100,
        changes,
        payments,
        payload.get("roi_treatment", "Recalculate EMI / Keep Tenure"),
    )
    pre_emi = pre_emi_interest(
        float(payload["principal"]),
        as_date(payload["disbursement"]),
        as_date(payload["first_emi"]),
        float(payload["roi"]) / 100,
    )
    return rows, controls, pre_emi, payload


def clear_schedule_state():
    for key in [
        "loaded_case_id", "loaded_payload", "schedule_result", "schedule_defaults",
        *SCHEDULE_WIDGET_KEYS,
    ]:
        st.session_state.pop(key, None)
    st.session_state.roi_events = []
    st.session_state.pp_events = []


def open_case(case):
    payload = normalize_payload(case)
    st.session_state.loaded_case_id = case["id"]
    st.session_state.loaded_payload = payload
    st.session_state.roi_events = payload.get("roi_events", [])
    st.session_state.pp_events = payload.get("pp_events", [])

    st.session_state.schedule_name = payload.get("name", "")
    st.session_state.schedule_account = payload.get("account_number", "")
    st.session_state.schedule_case_name = payload.get("case_name", "Loan Schedule")
    st.session_state.schedule_principal = float(payload.get("principal", 1_000_000))
    st.session_state.schedule_disbursement = as_date(payload.get("disbursement", date.today()))
    st.session_state.schedule_first_emi = as_date(payload.get("first_emi", date.today() + timedelta(days=30)))
    st.session_state.schedule_tenure = int(payload.get("tenure", 120))
    st.session_state.schedule_roi = float(payload.get("roi", 10.0))
    st.session_state.schedule_mode = payload.get("roi_treatment", "Recalculate EMI / Keep Tenure")

    # Rebuild and show the complete saved calculation immediately.
    st.session_state.schedule_result = calculation_from_payload(payload)
    st.session_state.pending_nav_page = "Repayment Schedule"


def auth_page(sb):
    render_logo()
    st.markdown(
        '<div class="hero"><h1>ASBS Loan Studio</h1>'
        '<p>EMI calculator, repayment schedules, ROI changes, part-payments and exports.</p></div>',
        unsafe_allow_html=True,
    )
    sign_in, create, forgot = st.tabs(["Sign in", "Create account", "Forgot password"])
    with sign_in:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign in", type="primary"):
            try:
                st.session_state.auth = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with create:
        email = st.text_input("Email", key="create_email")
        password = st.text_input("Password", type="password", key="create_password")
        if st.button("Create account"):
            try:
                sb.auth.sign_up({"email": email, "password": password})
                st.success("Account created. Confirm email if enabled, then sign in.")
            except Exception as exc:
                st.error(str(exc))
    with forgot:
        email = st.text_input("Registered email", key="forgot_email")
        if st.button("Send reset email"):
            try:
                sb.auth.reset_password_email(email, {"redirect_to": "https://asbs-loan.streamlit.app"})
                st.success("Recovery email sent.")
            except Exception as exc:
                st.error(str(exc))


def emi_page():
    st.markdown('<div class="hero"><h1>EMI Calculator</h1><p>Enter any three values. Annual basis is fixed at 365 days.</p></div>', unsafe_allow_html=True)
    target = st.selectbox("Calculate", ["EMI", "Principal", "Tenure", "ROI"])
    with st.form("emi_form"):
        a, b = st.columns(2)
        principal = a.number_input("Loan Principal (₹)", 0.0, 1e12, 5_451_215.0, 10_000.0, format="%.2f", disabled=target == "Principal")
        tenure = b.number_input("Tenure (months)", 0, 600, 45, 1, disabled=target == "Tenure")
        a, b = st.columns(2)
        roi = a.number_input("ROI (% p.a.)", 0.0, 100.0, 8.75, .5, format="%.2f", disabled=target == "ROI")
        emi = b.number_input("EMI (₹)", 0.0, 1e12, 0.0, 1000.0, format="%.2f", disabled=target == "EMI")
        calculate = st.form_submit_button("Calculate", type="primary", use_container_width=True)
    if calculate:
        try:
            st.session_state.emi_result = solve_missing(target, principal, int(tenure), roi, emi)
        except Exception as exc:
            st.error(str(exc))
    result = st.session_state.get("emi_result")
    if result:
        cols = st.columns(4)
        cols[0].metric("Principal", f"₹{result['principal']:,.2f}")
        cols[1].metric("Tenure", f"{result['tenure']} months")
        cols[2].metric("ROI", f"{result['roi_pct']:.2f}%")
        cols[3].metric("EMI", f"₹{result['emi']:,.2f}")
        if st.button("Use in Repayment Schedule"):
            clear_schedule_state()
            st.session_state.schedule_defaults = result
            st.session_state.nav_page = "Repayment Schedule"
            st.rerun()


def events_ui():
    roi_tab, payment_tab = st.tabs(["ROI Changes", "Part Payments"])
    with roi_tab:
        with st.form("roi_event", clear_on_submit=True):
            a, b, c = st.columns(3)
            day = a.date_input("Effective date")
            rate = b.number_input("New ROI (%)", 0.0, 100.0, 10.0, .5, format="%.2f")
            note = c.text_input("Note")
            if st.form_submit_button("Add ROI change"):
                st.session_state.roi_events.append({"date": day.isoformat(), "rate": rate, "note": note})
                st.session_state.schedule_result = None
                st.rerun()
        for index, item in enumerate(st.session_state.roi_events):
            a, b = st.columns([8, 1])
            a.info(f"{item['date']} · {item['rate']:.2f}% · {item.get('note') or 'No note'}")
            if b.button("Remove", key=f"remove_roi_{index}"):
                st.session_state.roi_events.pop(index)
                st.session_state.schedule_result = None
                st.rerun()
    with payment_tab:
        with st.form("payment_event", clear_on_submit=True):
            a, b, c, d = st.columns(4)
            day = a.date_input("Payment date")
            amount = b.number_input("Amount (₹)", .01, step=1000.0, format="%.2f")
            effect = c.selectbox("Effect", ["Reduce Tenure", "Reduce EMI"])
            note = d.text_input("Note")
            if st.form_submit_button("Add part-payment"):
                st.session_state.pp_events.append({"date": day.isoformat(), "amount": amount, "effect": effect, "note": note})
                st.session_state.schedule_result = None
                st.rerun()
        for index, item in enumerate(st.session_state.pp_events):
            a, b = st.columns([8, 1])
            a.info(f"{item['date']} · ₹{item['amount']:,.2f} · {item['effect']} · {item.get('note') or 'No note'}")
            if b.button("Remove", key=f"remove_pp_{index}"):
                st.session_state.pp_events.pop(index)
                st.session_state.schedule_result = None
                st.rerun()


def schedule_page(sb, user):
    defaults = st.session_state.get("schedule_defaults", {})
    payload = st.session_state.get("loaded_payload", {})
    st.markdown('<div class="hero"><h1>Repayment Schedule</h1><p>Open, edit, recalculate, export and save the complete case.</p></div>', unsafe_allow_html=True)

    st.session_state.setdefault("schedule_name", payload.get("name", ""))
    st.session_state.setdefault("schedule_account", payload.get("account_number", ""))
    st.session_state.setdefault("schedule_case_name", payload.get("case_name", "Loan Schedule"))
    st.session_state.setdefault("schedule_principal", float(payload.get("principal", defaults.get("principal", 1_000_000))))
    st.session_state.setdefault("schedule_disbursement", as_date(payload["disbursement"]) if payload.get("disbursement") else date.today())
    st.session_state.setdefault("schedule_first_emi", as_date(payload["first_emi"]) if payload.get("first_emi") else date.today() + timedelta(days=30))
    st.session_state.setdefault("schedule_tenure", int(payload.get("tenure", defaults.get("tenure", 120))))
    st.session_state.setdefault("schedule_roi", float(payload.get("roi", defaults.get("roi_pct", 10))))
    st.session_state.setdefault("schedule_mode", payload.get("roi_treatment", "Recalculate EMI / Keep Tenure"))

    a, b, c = st.columns(3)
    name = a.text_input("Name", key="schedule_name")
    account = b.text_input("Account Number", key="schedule_account")
    case_name = c.text_input("Case Name", key="schedule_case_name")
    a, b, c = st.columns(3)
    principal = a.number_input("Principal (₹)", min_value=1.0, step=10_000.0, format="%.2f", key="schedule_principal")
    disbursement = b.date_input("Disbursement Date", key="schedule_disbursement")
    first_emi = c.date_input("First EMI Date", key="schedule_first_emi")
    a, b, c = st.columns(3)
    tenure = a.number_input("Tenure (months)", min_value=1, max_value=600, step=1, key="schedule_tenure")
    roi = b.number_input("Initial ROI (%)", min_value=0.0, max_value=100.0, step=.5, format="%.2f", key="schedule_roi")
    mode = c.selectbox("ROI Treatment", ["Recalculate EMI / Keep Tenure", "Keep EMI / Reduce Tenure"], key="schedule_mode")

    events_ui()
    actions = st.columns([3, 1])
    recalculate = actions[0].button("Recalculate Schedule", type="primary")
    if actions[1].button("Start New Case"):
        clear_schedule_state()
        st.rerun()

    if recalculate:
        current_payload = {
            "case_name": case_name.strip() or "Loan Schedule",
            "name": name.strip(),
            "account_number": account.strip(),
            "principal": rupee(principal),
            "disbursement": disbursement.isoformat(),
            "first_emi": first_emi.isoformat(),
            "tenure": int(tenure),
            "roi": float(roi),
            "roi_treatment": mode,
            "roi_events": st.session_state.roi_events,
            "pp_events": st.session_state.pp_events,
        }
        try:
            st.session_state.loaded_payload = current_payload
            st.session_state.schedule_result = calculation_from_payload(current_payload)
        except Exception as exc:
            st.error(str(exc))

    result = st.session_state.get("schedule_result")
    if not result:
        st.info("Edit the saved inputs or events, then select Recalculate Schedule.")
        return

    rows, controls, pre_emi, result_payload = result
    # Descriptive fields always follow the live inputs; no recalculation is needed for these.
    result_payload = dict(result_payload)
    result_payload.update({"name": name.strip(), "account_number": account.strip(), "case_name": case_name.strip() or "Loan Schedule"})
    st.session_state.schedule_result = (rows, controls, pre_emi, result_payload)

    metrics = st.columns(7)
    values = [
        ("Initial EMI", f"₹{controls['initial_emi']:,.2f}"),
        ("Interest", f"₹{controls['total_interest']:,.2f}"),
        ("Part Payments", f"₹{controls['total_prepayment']:,.2f}"),
        ("Variance", f"₹{controls['principal_variance']:,.2f}"),
        ("Schedule Rows", str(controls["schedule_rows"])),
        ("Payoff", controls["payoff_date"].strftime("%d-%m-%Y")),
        ("Control", controls["status"]),
    ]
    for column, (label, value) in zip(metrics, values):
        column.metric(label, value)

    frame = pd.DataFrame([
        {
            "EMI #": row.emi_no, "Due Date": row.due_date,
            "Opening Principal": row.opening_principal, "ROI (% p.a.)": row.roi * 100,
            "Interest Component": row.interest_component, "Principal Component": row.principal_component,
            "EMI": row.emi, "Part Prepayment": row.part_prepayment,
            "Closing Principal": row.closing_principal,
        }
        for row in rows
    ])
    money = ["Opening Principal", "Interest Component", "Principal Component", "EMI", "Part Prepayment", "Closing Principal"]
    config = {column: st.column_config.NumberColumn(format="₹ %.2f") for column in money}
    config["ROI (% p.a.)"] = st.column_config.NumberColumn(format="%.2f")
    st.dataframe(frame, use_container_width=True, hide_index=True, column_config=config)

    pdf = build_pdf(LOGO, result_payload, pre_emi, controls, rows)
    excel = build_excel(result_payload, pre_emi, controls, rows, st.session_state.roi_events, st.session_state.pp_events)
    basename = f"ASBS_RPS_{safe_filename(result_payload['account_number'])}"
    buttons = st.columns(3)
    buttons[0].download_button("Download PDF", pdf, f"{basename}.pdf", "application/pdf")
    buttons[1].download_button("Download Excel", excel, f"{basename}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if buttons[2].button("Save Changes" if st.session_state.get("loaded_case_id") else "Save Case"):
        record = {
            "user_id": user.id,
            "case_name": result_payload["case_name"],
            "borrower": result_payload["name"],
            "loan_reference": result_payload["account_number"],
            "payload": result_payload,
        }
        try:
            case_id = st.session_state.get("loaded_case_id")
            if case_id:
                sb.table("loan_cases").update(record).eq("id", case_id).execute()
            else:
                response = sb.table("loan_cases").insert(record).execute()
                if response.data:
                    st.session_state.loaded_case_id = response.data[0]["id"]
            st.session_state.loaded_payload = result_payload
            st.success("Case saved with the complete calculation. The case can be reopened and recalculated.")
        except Exception as exc:
            st.error(f"Save failed: {exc}")


def saved_cases_page(sb, user):
    st.markdown('<div class="hero"><h1>Saved Cases</h1><p>Search, open the complete calculation, edit and recalculate.</p></div>', unsafe_allow_html=True)
    query = st.text_input("Search by Account Number or Name", placeholder="Type account number or name")
    try:
        cases = sb.table("loan_cases").select("*").eq("user_id", user.id).order("updated_at", desc=True).execute().data
    except Exception as exc:
        st.error(str(exc))
        return
    needle = query.strip().lower()
    if needle:
        cases = [case for case in cases if needle in str(case.get("loan_reference", "")).lower() or needle in str(case.get("borrower", "")).lower() or needle in str(case.get("case_name", "")).lower()]
    st.caption(f"{len(cases)} case(s) found")
    for case in cases:
        a, b, c = st.columns([5, 1, 1])
        a.markdown(f"**Account: {case.get('loan_reference') or '-'}**  \nName: {case.get('borrower') or '-'} · {case.get('case_name') or '-'}")
        if b.button("Open / Edit", key=f"open_{case['id']}"):
            try:
                open_case(case)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not open calculation: {exc}")
        if c.button("Delete", key=f"delete_{case['id']}"):
            sb.table("loan_cases").delete().eq("id", case["id"]).execute()
            st.rerun()


def main(sb):
    # Apply requested navigation before the radio widget is created.
    if "pending_nav_page" in st.session_state:
        st.session_state.nav_page = st.session_state.pop("pending_nav_page")
    st.session_state.setdefault("nav_page", "EMI Calculator")
    st.session_state.setdefault("roi_events", [])
    st.session_state.setdefault("pp_events", [])
    user = st.session_state.auth.user
    with st.sidebar:
        render_logo(sidebar=True)
        st.radio("Workspace", PAGES, key="nav_page")
        st.caption(user.email)
        if st.button("Sign out"):
            sb.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    page = st.session_state.nav_page
    if page == "EMI Calculator":
        emi_page()
    elif page == "Repayment Schedule":
        schedule_page(sb, user)
    elif page == "Saved Cases":
        saved_cases_page(sb, user)
    else:
        st.header("Profile")
        st.write(user.email)


sb = supabase_client()
if "auth" in st.session_state:
    try:
        session = st.session_state.auth.session
        restored = sb.auth.set_session(session.access_token, session.refresh_token)
        if restored and restored.session:
            st.session_state.auth = restored
    except Exception:
        st.session_state.pop("auth", None)
        st.rerun()

if "auth" not in st.session_state:
    auth_page(sb)
else:
    main(sb)
