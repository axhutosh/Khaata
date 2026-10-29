# Khaata — project guide for Claude Code

Read this first. It orients you to the project, the plan, and the conventions.

## What this is

A personal spend tracker. The user uploads an SBI bank-statement PDF (password-protected
is fine), and Khaata decrypts it, extracts transactions, balance-checks them, categorises
merchants, and shows daily / monthly / yearly insights. **Solo, single-user v1.**

## The plan lives in `docs/`

- **`docs/PRD.md`** — scope, non-goals, user journey, data model, insights spec, parsing
  pipeline, tech stack, locked decisions, build phases. This is the source of truth.
- **`docs/DESIGN.md`** — design system (tokens, palette, type) and the six screens.

Read both before making design or scope decisions. If a change contradicts a locked
decision in the PRD, flag it rather than silently diverging.

## Locked decisions (do not re-litigate without asking)

- Store transactions in a DB (history across uploads powers daily/monthly/yearly).
- User types the statement password; used once to decrypt, **never stored**. No PAN/DOB auto-guessing in v1.
- SIP → **Investments** (excluded from spend); EMIs → spend (Bills/Loan). Both show under recurring.
- Daily/Monthly/Yearly toggle is on the **Dashboard only**; Transactions uses date-range + search.
- Upload is a **one-time onboarding** step; returning users land on the Dashboard.
- One bank at a time, **SBI first**. Perfect SBI before adding a second bank.

## Architecture

- `backend/` — FastAPI. Entry: `app/main.py`. Each query is scoped to `user_id`.
  - `app/extractor.py` — the bank-specific pipeline: decrypt → parse → categorise → balance-check.
    **Adding a bank = a new narration normaliser + table reader here.** Everything downstream is bank-agnostic.
  - `app/insights.py` — all aggregation (derived live from the `transactions` table).
  - `app/models.py` — `User`, `Transaction`, `MerchantRule`, `Budget`.
  - `app/routers/` — auth, upload, transactions, insights, budgets.
- `frontend/` — Vite + React. API client in `src/api.js` (proxied `/api` → backend).
  Pages in `src/pages/`, shared shell in `src/components/Shell.jsx`, tokens in `src/styles.css`.

## Conventions

- Money is `numeric`, stored as a positive magnitude with a `debit`/`credit` type — never a signed float.
- Keep the extractor pure/testable: bytes in, structured `ParsedTxn` out. No DB calls inside it.
- Categorisation order is cheap→expensive (rules → fuzzy → LLM). Don't call an LLM before the rules miss.
- A user's category correction writes a `MerchantRule` and retro-applies — keep that behaviour.
- Frontend: use the existing `card` / `nav` / `btn` / `pill` classes and `inr()`; don't restyle per page.
- Colour never carries meaning by hue alone (accessibility).

## Current status

Phase-1 spine is built and verified against a **synthetic** SBI statement
(`backend/samples/SBI_sample_locked.pdf`, password `ASHUT1947`): auth, upload+decrypt,
extractor, transactions, insights, recurring, budgets, dedupe all work; balance check
reconciles to ₹0.00. The per-requirement status table, known issues and open questions
live in **`docs/PRD.md` §9** — keep it current as things ship.

**Next up (Phase-1 finish):**
1. Replace the synthetic statement with a real (redacted) SBI PDF and tighten
   `app/extractor.py` regexes to its exact layout (date format, wrapped narrations, column widths).
2. Add the explicit Review-before-save step: split `/upload` into `/upload/preview` (parse,
   return rows, save nothing) and `/upload/commit` (save reviewed rows). The Review screen gates the save.
3. Then Phase 2 per the PRD (alerts, export, richer views).

## Run

See `README.md`. Backend: `uvicorn app.main:app --reload`. Frontend: `npm run dev`.
