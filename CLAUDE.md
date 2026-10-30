# Khaata — project guide for Claude Code

Read this first. It orients you to the project, the plan, and the conventions.

## What this is

A personal spend tracker. The user uploads an SBI bank-statement PDF (password-protected
is fine), and Khaata decrypts it, extracts transactions, balance-checks them, categorises
merchants, and shows daily / monthly / yearly insights. **Open sign-up (email + password); each user's data is isolated.**

## The plan lives in `docs/`

- **`docs/PRD.md`** — scope, non-goals, user journey, data model, insights spec, parsing
  pipeline, tech stack, locked decisions, build phases. This is the source of truth.
- **`docs/DESIGN.md`** — design system (tokens, palette, type) and the six screens.

Read both before making design or scope decisions. If a change contradicts a locked
decision in the PRD, flag it rather than silently diverging.

## Locked decisions (do not re-litigate without asking)

- Store transactions in a DB (history across uploads powers daily/monthly/yearly).
- User types the statement password; used once to decrypt, **never stored**. No PAN/DOB auto-guessing in v1.
- **Sign-in is email + password with open sign-up** (`OPEN_SIGNUP`, default on). Google sign-in was removed until the app is hosted on a verified domain. Every query must stay scoped to `user_id` — `tests/test_isolation.py` guards it.
- **README.md is product + branding only** — no setup or dev guides there; those live in `docs/SETUP.md`.
- The UI says **SBI only**, other banks "coming soon" (Upload page).
- SIP → **Investments** (excluded from spend); EMIs → spend (Bills/Loan). Both show under recurring.
- Daily/Monthly/Yearly toggle is on the **Dashboard only**; Transactions uses date-range + search.
- Upload is a **one-time onboarding** step; returning users land on the Dashboard.
- One bank at a time, **SBI first**. Perfect SBI before adding a second bank.

## Architecture

- `backend/` — FastAPI. Entry: `app/main.py`. Each query is scoped to `user_id`.
  - `app/extractor.py` — the bank-specific pipeline: decrypt → parse → categorise → balance-check.
    **Adding a bank = a new narration normaliser + table reader here.** Everything downstream is bank-agnostic.
  - `app/insights.py` — all aggregation (derived live from the `transactions` table).
  - `app/models.py` — `User`, `Upload`, `Transaction`, `MerchantRule`, `Budget`.
  - `app/rules.py` — merchant rules: load a user's rules, `learn()` a correction (write rule + retro-apply), `reclassify()` saved rows.
  - `app/names.py` — person-vs-business signals (first names, surnames, business words, merchant-VPA hints) for P2P detection.
  - `app/crypto.py` — `raw_narration` encrypted at rest (Fernet, `DATA_KEY`), keyed dedupe hash, startup migration/rotation. Never filter `raw_narration` in SQL — it's ciphertext.
  - `app/security.py` — security headers, CSRF origin check, login throttle. `app/auth.py` — sessions. `app/passwords.py` — scrypt hashing + password rules.
  - `app/routers/` — auth (sign-up / sign-in), upload (`/preview` + `/commit`), uploads (list/delete), transactions, insights, budgets.
    **New routers go under `dependencies=[Depends(current_user)]` in `main.py`**; `tests/test_security.py` fails any route that answers without a session.
  - `tests/` — pytest against the sample PDFs; run `python -m pytest` from `backend/`.
- `frontend/` — Vite + React. API client in `src/api.js` (proxied `/api` → backend).
  Pages in `src/pages/`, shared shell in `src/components/Shell.jsx`, tokens in `src/styles.css`.

## Conventions

- Money is `numeric`, stored as a positive magnitude with a `debit`/`credit` type — never a signed float.
- Keep the extractor pure/testable: bytes in, structured `ParsedTxn` out. No DB calls inside it.
- Categorisation order is cheap→expensive (rules → fuzzy → LLM). Don't call an LLM before the rules miss.
- A user's category correction writes a `MerchantRule` and retro-applies — keep that behaviour.
- Frontend: use the existing `card` / `nav` / `btn` / `pill` classes and `inr()`; don't restyle per page.
- Colour never carries meaning by hue alone (accessibility).

## Current status (2026-10-31)

Working end to end locally and verified against a **real** (masked) SBI statement: 57/57 rows,
balance check reconciles to ₹0.00. ~114 backend tests. The per-requirement status table, known
issues and open questions live in **`docs/PRD.md` §9** — keep it current as things ship.

**Built:**
- **Statements**: SBI PDF (locked or not) and Excel; real SBI UPI layout (wrapped narrations,
  `WDL TFR … AT <branch>` trailer, Statement Summary for opening/closing); Review-before-save
  (preview/commit); dedupe; delete an upload.
- **Categorisation**: seed merchants → fuzzy → trade keywords; P2P vs merchant scoring
  (`names.py`, phone-number/QR VPAs, business words); learned rules from corrections; re-run on
  saved rows (`POST /transactions/reclassify`).
- **Insights**: Dashboard (money in/out, P2P vs shops, categories, people, weekday, small spends,
  balance trend, largest payments, "What Khaata noticed"); Subscriptions (`recurring.py`: cadence,
  next charge, price changes, may-have-stopped, frequent places); Transactions (filters, grouped
  by day); per-month Budgets.
- **Accounts & security**: email + password with open sign-up and strong new-password rules
  (`passwords.py`, mirrored in `frontend/src/passwordRules.js`); every API needs a session;
  per-user isolation test; CSRF origin check; throttling; security headers; narrations
  encrypted at rest (`crypto.py`, `DATA_KEY`).
- **Brand**: logo, favicon, app icons (`branding/`, `frontend/scripts/make_brand.py`).
  README is product + brand only; dev guide in `docs/SETUP.md`.

**Next up:**
1. **Hosting** (planned next session): one container on Railway (FastAPI serves the built
   frontend) + managed Postgres with backups; a domain the owner buys; `/privacy` and `/terms`
   pages; a "Delete my account and data" option. Not Vercel (4.5 MB request limit, no disk).
2. After hosting: Google sign-in again (needs the verified domain + privacy/terms), Alembic.
3. Extractor: still only UPI rows tested on a real statement — get masked statements with
   NEFT/IMPS/ATM/ACH/charges/interest, and a real SBI Excel export. Real statements go in
   `backend/samples/real/` (git-ignored; the repo is **public**), masked with
   `tools/mask_statement.py`; only read the `.masked.*` files.
4. Phase 2 leftovers: CSV/PDF export, Budgets page polish (category picker, history),
   browser UI pass over every screen.

## Run

See `docs/SETUP.md`. Backend: `uvicorn app.main:app --reload --reload-dir app` (without `--reload-dir` it also watches `.venv`). On this Windows setup the reloader has missed edits — after changing backend code, restart it and confirm the change is live. Frontend: `npm run dev`.
