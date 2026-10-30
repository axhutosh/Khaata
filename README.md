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
pip install -r requirements-dev.txt   # app deps + pytest
cp .env.example .env            # set SECRET_KEY, SEED_EMAIL and GOOGLE_CLIENT_ID
uvicorn app.main:app --reload --reload-dir app   # http://localhost:8000  (docs at /docs)
```

On first run it creates the SQLite DB and seeds one user from `.env`.

**2. Frontend** (Node 18+)

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api/*` to the backend, so sessions are same-origin.

**3. Tests**

```bash
cd backend
python -m pytest
```

Uses a throwaway SQLite DB and the sample PDFs. There are no migrations yet: after a schema
change, delete `backend/khaata.db` and restart.

## Try the flow

1. Open http://localhost:5173 and continue with Google (set up below under Security).
2. Upload `backend/samples/SBI_sample_locked.pdf` — password **`ASHUT1947`**.
3. Review the parsed rows (balance check banner, categories, duplicates) and fix any category —
   nothing is saved until **Looks good — save**. Then land on the Dashboard.
4. Try the Daily / Monthly / Yearly toggle, Transactions, Subscriptions, Budgets.

(`SBI_sample.pdf` is the same statement without a password, to test the unlocked path.)

## Security

- **Sign-in is Google only.** There are no passwords to guess, reuse or leak. Any verified
  Google account can sign up (`OPEN_SIGNUP=true`, the default) and gets its own account; set
  `OPEN_SIGNUP=false` to allow only `ALLOWED_EMAILS`.
- **Accounts are sealed off from each other.** Every query is scoped to the signed-in user;
  `tests/test_isolation.py` proves one user can't read, change, delete or replay another's data.
- **Every API needs a session** except sign-in (`/auth/google`, `/auth/config`, `/auth/logout`)
  and `/health`. Enforced per router in `app/main.py` and checked by a test that
  walks every route.
- **Session**: signed, HttpOnly, SameSite=Lax cookie (`khaata_session`), 7 days by default;
  `Secure` (HTTPS-only) in production. Signing in starts a fresh session.
- **Cross-site requests**: writes from an origin outside `CORS_ORIGINS` are refused (CSRF).
- **Throttling**: 5 failed Google sign-ins from one address in 15 minutes pauses sign-in from
  that address for the rest of the window (other addresses, including yours, are unaffected).
- **Uploads**: capped at `MAX_UPLOAD_MB`; the statement password is used once and never stored.
- **Responses**: `no-store`, `nosniff`, `DENY` framing, a locked-down CSP. `/docs` is off in production.
- **Production** (`ENV=production`) refuses to start with the placeholder `SECRET_KEY`, no
  `GOOGLE_CLIENT_ID`, or non-HTTPS cookies.

### Google sign-in

1. In [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials),
   create an **OAuth client ID**, type **Web application**.
2. Under **Authorized JavaScript origins** add `http://localhost:5173` (and your real domain later).
   No redirect URI is needed.
3. Put the client ID in `backend/.env` as `GOOGLE_CLIENT_ID=…apps.googleusercontent.com` and
   restart the backend.
4. **To let other people sign in**, open **OAuth consent screen** in the same console and
   **Publish app** (move it from "Testing" to "In production"). While it's in Testing, only the
   test users you list there can sign in. Khaata asks only for name and email, which don't need
   Google's app verification.

The login page shows "Continue with Google" — the only way in; for someone new, the same button creates their account. The backend verifies Google's signed ID token
(signature, audience, expiry, verified email). The first sign-in creates that person's account
and links their Google account to it; a different Google account for the same email is refused.

## Sharing a real statement safely

To tune the extractor to a real SBI layout without sharing personal data:

```bash
cd backend
.venv\Scripts\activate
# put the PDF in backend/samples/real/  (git-ignored)
python tools/mask_statement.py samples/real/statement.pdf
```

It asks for the PDF password (not shown, not stored) and writes `statement.masked.txt` and
`statement.masked.json` next to it. Names, account/reference numbers, UPI IDs, IFSC and address
become placeholders (`XXXX`, `9999`); dates, amounts, balances, SBI layout words and well-known
business names stay. **Read the .txt before sharing.** Use `--keep WORD,WORD` to leave more
business names visible.

## Decisions baked in (from the PRD)

- **Password:** entered by the user, used once to decrypt, never stored.
- **SIP → Investments** (excluded from spend); EMIs count as spend; both show under recurring.
- **Time toggle** on the Dashboard; Transactions uses date-range/search instead.
- **Onboarding** (Upload) is a first-run step; returning users land on the Dashboard.

## Next

- Replace the synthetic statement with a real (redacted) SBI PDF and tighten `extractor.py`
  regexes against its exact layout (date format, wrapped narrations, column widths).
- Add alerts (large spend, new merchant, bank fees) and CSV/PDF export.
- When adding a second bank, write a new normaliser in `extractor.py`; everything downstream is bank-agnostic.
```
