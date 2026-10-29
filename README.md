# Khaata — Spend Tracker

Upload an SBI bank-statement PDF (password-protected is fine), and Khaata decrypts it,
extracts transactions, balance-checks them, categorises merchants, and shows daily /
monthly / yearly insights. Solo, single-user v1.

This repo is the Phase-1 scaffold: a working backend (FastAPI + the SBI extractor +
insight queries) and a React frontend wired to it.

**The plan lives in the repo:**
- `CLAUDE.md` — orientation for a Claude Code session (architecture, decisions, conventions, what's next).
- `docs/PRD.md` — scope, data model, insights, parsing pipeline, decisions, build phases.
- `docs/DESIGN.md` — design system and the six screens.

```
khaata-app/
├── backend/            FastAPI app
│   ├── app/
│   │   ├── main.py         app + middleware + routers
│   │   ├── config.py       settings (env)
│   │   ├── database.py     SQLAlchemy engine/session (SQLite default)
│   │   ├── models.py       User, Transaction, MerchantRule, Budget
│   │   ├── auth.py         session login + password hashing
│   │   ├── extractor.py    decrypt → parse → categorise → balance check  (SBI)
│   │   ├── insights.py     daily/monthly/yearly, categories, recurring, budgets
│   │   └── routers/        auth, upload, transactions, insights, budgets
│   ├── samples/        synthetic SBI statements for testing
│   └── requirements.txt
└── frontend/           Vite + React
    └── src/
        ├── api.js          API client (proxied to backend)
        ├── App.jsx         routes + auth guard
        ├── components/Shell.jsx
        └── pages/          Login, Upload, Dashboard, Transactions, Subscriptions, Budgets
```

## Run it

**1. Backend** (Python 3.11+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit SEED_EMAIL / SEED_PASSWORD / SECRET_KEY
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

On first run it creates the SQLite DB and seeds one user from `.env`.

**2. Frontend** (Node 18+)

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api/*` to the backend, so sessions are same-origin.

## Try the flow

1. Open http://localhost:5173 and sign in with your seed email/password.
2. Upload `backend/samples/SBI_sample_locked.pdf` — password **`ASHUT1947`**.
3. Watch the balance check pass, then land on the Dashboard with real insights.
4. Try the Daily / Monthly / Yearly toggle, Transactions, Subscriptions, Budgets.

(`SBI_sample.pdf` is the same statement without a password, to test the unlocked path.)

## Decisions baked in (from the PRD)

- **Password:** entered by the user, used once to decrypt, never stored.
- **SIP → Investments** (excluded from spend); EMIs count as spend; both show under recurring.
- **Time toggle** on the Dashboard; Transactions uses date-range/search instead.
- **Onboarding** (Upload) is a first-run step; returning users land on the Dashboard.

## Next

- Replace the synthetic statement with a real (redacted) SBI PDF and tighten `extractor.py`
  regexes against its exact layout (date format, wrapped narrations, column widths).
- Add the explicit Review-before-save step (split `/upload` into `/preview` + `/commit`).
- Add alerts (large spend, new merchant, bank fees) and CSV/PDF export.
- When adding a second bank, write a new normaliser in `extractor.py`; everything downstream is bank-agnostic.
```
