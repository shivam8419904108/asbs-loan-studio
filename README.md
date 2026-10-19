# ASBS Loan Studio V4

## Fixed convention
- Regular EMI basis: 30 days
- Annual basis: 365 days only
- Periodic rate = annual ROI x 30 / 365

## Streamlit secrets
```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
```

Upload `app.py`, `finance_engine.py`, `asbs-logo.png`, and `requirements.txt` to GitHub. The EMI Calculator is the first page after login. Supabase Auth makes the same account available on another mobile or laptop.
