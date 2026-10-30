# Khaata — Spend Tracker PRD (v1)

_As of 2026-10-30 · Owner: Ashutosh_

> Source of truth for scope and decisions. Canonical doc (editable):
> https://claude.ai/artifact/LV6KjfYBXH8iiHagUMKDPM
> Code: https://github.com/axhutosh/Khaata

## 1. Overview & goals

Khaata turns a bank-statement PDF into a clear picture of where money goes. The user signs in, uploads a statement (password-protected is fine), reviews the parsed transactions, and gets daily, monthly and yearly insights.

- **User (v1):** just the builder, single account. Public multi-user is a later decision, made only after the insights prove useful in real use.
- **Core promise:** upload once, see everything — categories, top merchants, subscriptions, trends, budgets and alerts — with numbers the user can trust (every statement is balance-checked on import).
- **Primary input:** PDF statements (full history in one file). SMS capture and the Account Aggregator framework are explicitly deferred.

## 2. Scope & non-goals (v1)

**In scope**

- Email/password + Google sign-in; single user with their own session.
- Upload bank-statement PDFs, including password-protected (user enters the password).
- Decrypt, extract transactions, balance-check, store in a database.
- Review screen to fix mis-categorised rows before saving.
- Insights: daily / monthly / yearly overview, category & merchant breakdown, recurring/subscriptions, budgets, alerts.
- Merchant cleanup and auto-categorisation that learns from the user's corrections.
- Multi-month and multi-upload support with duplicate removal.
- Export (CSV / PDF report).

**Out of scope (v1)**

- Credit cards, wallets, multiple banks beyond the user's own account(s).
- SMS-based capture; Account Aggregator / live bank connections.
- Password auto-guessing from PAN/DOB (user types the password instead).
- Scanned-image statements / OCR.
- Multi-user, sharing, mobile apps, forecasting beyond a simple month-end projection.

## 3. User journey

**One-time onboarding** (first run only; Upload lives here, not in the main nav):

1. Sign in (email/password or Google).
2. Upload a statement PDF — ideally several months in one file.
3. If the PDF is locked, enter its password; Khaata decrypts in memory.
4. Khaata extracts transactions and runs the balance check.
5. Review the parsed table; fix any flagged categories; save.
6. Land on the Dashboard with insights ready.

**Ongoing (returning user):**

- Lands directly on the Dashboard.
- Each month (or whenever), uploads a new statement via a secondary action; duplicates are removed, history deepens.
- Explores Transactions, Subscriptions and Budgets; corrects categories as needed, which the system remembers.

## 4. Features & requirements by screen

Six screens, matching the approved designs (see `DESIGN.md`).

| Screen | Purpose | Key requirements |
| --- | --- | --- |
| Login | Authenticate | Email/password + Google; session cookie; first-run users → onboarding, returning users → Dashboard |
| Onboarding: Upload & Unlock | Get the statement in | Drag/drop PDF; detect encryption; password field with bank-specific hint; decrypt in memory; wrong-password retry; accept multiple files |
| Review | Trust the data | Parsed table (date, merchant, raw narration, category, amount); balance-check banner (opening + credits − debits = closing); flag uncategorised rows; inline category edit; save all |
| Dashboard | The insights home | Daily/Monthly/Yearly toggle; KPIs (income, spent, saved, daily avg); income-vs-spend trend; category donut; top merchants; "what Khaata noticed" alerts |
| Subscriptions | Recurring view | Auto-detected recurring payments; cadence, next-charge date, amount; price-increase flag; SIP tagged as investment, not spend |
| Budgets | Control spending | Overall budget vs actual + month-end projection; per-category budgets with progress; over/near/under states |

Transactions (reached from the Dashboard nav) is a full, searchable, date-range-filterable list of the same saved rows; it reuses the Review table components.

## 5. Data model & insights

One fine-grained table is the source of truth; every insight is a query over it. Aggregates are computed on the fly, never stored as the source.

**`transactions`**

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid | Primary key |
| user_id | uuid | Owner; every query filters on this |
| txn_date | date | Transaction date |
| amount | numeric | Positive magnitude |
| type | enum | debit / credit |
| balance | numeric | Running balance from statement (for balance check) |
| raw_narration | text | Original messy string from the PDF |
| merchant | text | Cleaned merchant name |
| category | text | Assigned category |
| method | text | UPI / NEFT / ACH / ATM / INB / FEE / OTHER, from the narration |
| counterparty_kind | text | merchant / person / self / bank — drives person-vs-merchant on Review |
| is_recurring | bool | Set by subscription detection |
| source_file | text | Which upload it came from |
| txn_hash | text | For duplicate detection across uploads; unique per (user_id, txn_hash) |

Supporting tables: `users` (email, password_hash, `onboarded` flag that routes first-run vs returning), `uploads` (one per committed statement: filename, period, saved/duplicate counts, whether it balanced; `transactions.upload_id` points here), `merchant_rules` (user_id, narration token → merchant + category, grows from corrections), `budgets` (user_id, category, monthly_limit; one per category).

**Duplicate key.** `txn_hash = sha256(user_id | txn_date | amount | type | raw_narration)`. SBI narrations carry a reference number, so genuine repeats normally differ; two rows that are byte-identical will collapse into one (see §9).

**Category taxonomy.** Spend categories: Food & Dining, Shopping, Groceries, Bills & Utilities, Entertainment, Transport, Insurance, Cash, Bank Fees, Uncategorised. Non-spend categories (excluded from spend totals, category donut and top merchants): **Income**, **Investments**, **Transfer · Person**, **Cashback**. Income KPIs count only credits categorised as Income — refunds and transfers in do not inflate income.

**Insights computed from this table**

- **Daily / Monthly / Yearly:** group by day / year-month / year — income, spend, net, savings rate.
- **Category & merchant:** sum and rank by category and by merchant; top-N.
- **Recurring:** merchants repeating at a regular interval with a similar amount → cadence + next-charge estimate; flag amount increases.
- **Habits:** spend by day-of-week; count of small frequent spends.
- **Cash flow:** salary date, balance low points, projected days-to-low.
- **Alerts:** unusually large spend, new merchant, duplicate charge, bank fees/penalties.
- **Budgets:** actual vs limit per category; simple linear month-end projection.

## 6. Parsing & categorisation pipeline

The flow for every upload: **decrypt → extract → balance-check → clean & categorise → dedupe → save.**

**Decrypt.** `pikepdf` opens the PDF with the user-supplied password; parse the decrypted copy in memory; discard password and original after parsing.

**Extract.** Per-bank parser pulls date, amount, debit/credit, narration and running balance from the statement layout. Start with the user's own bank (SBI first). Cashiro (open-source) has regex patterns for 80+ banks that port directly to Python — reuse its pattern for the target bank rather than writing from scratch.

**Balance check.** opening balance + credits − debits must equal closing balance; if it doesn't, warn the user that a row may have been mis-read.

**Merchant cleanup & categorisation** — a cheap-to-expensive pipeline; most rows stop early:

1. **Normalise** — detect txn type (UPI / POS / NEFT / IMPS / ACH / ATM), strip reference numbers, IFSC and terminal IDs, pull the merchant/VPA token.
2. **Rules dictionary** — known-merchant map (`swiggy`/`bundl technologies` → Swiggy / Food), seeded with the ~100 merchants that cover most spend.
3. **Fuzzy match** — `rapidfuzz` catches near-misses against the dictionary, above a confidence threshold.
4. **LLM fallback** — only the leftovers go to an LLM for merchant + category; cache the result into the dictionary so it's free next time.
5. **Learn from corrections** — a category fixed on the Review screen is saved as a rule and applied to future uploads.

Since it's one user, the merchant set is small and repetitive, so the dictionary converges quickly and the LLM is rarely needed.

## 7. Tech stack & locked decisions

| Layer | Choice | Why |
| --- | --- | --- |
| Backend / API | Python + FastAPI | Parsing & data wrangling live in Python; FastAPI is lean and async |
| Parsing | pdfplumber / PyMuPDF + pikepdf | PDF extraction + decryption |
| Aggregation | pandas + SQL | Insight math |
| Database | PostgreSQL (SQLite to start) | One clean transactions table; good date grouping |
| Auth | Session-based login | Each query scoped to user_id |
| Frontend | React (Vite) | Rich interactive charts; matches the approved UI |

**Locked decisions**

- **Storage:** yes — transactions are stored so daily/monthly/yearly history works across uploads.
- **Password handling:** user types the statement password; used once to decrypt, never stored. No auto-guessing from PAN/DOB in v1.
- **SIP vs EMI:** SIPs count as **Investments** (wealth, excluded from spend so savings rate stays honest); EMIs count as spend under Bills/Loan. Both still appear under recurring.
- **Time toggle:** Daily/Monthly/Yearly lives on the Dashboard only; Transactions uses a date-range filter instead.
- **Onboarding:** Upload is a one-time first-run flow; returning users land on the Dashboard and upload via a secondary action.
- **Privacy:** original PDF and password discarded after parsing; stored transaction data encrypted at rest.
- **Encryption at rest (decided 2026-10-30):** column-level encryption of `raw_narration` (it holds VPAs, account fragments, reference numbers and people's names) with Fernet, via a SQLAlchemy type, key from a `DATA_KEY` env var that never enters the DB. `merchant`, `category`, `amount` and dates stay plaintext so SQL can group and sum them; narration search moves into Python (fine at one user's volume). Chosen over SQLCipher because it builds cleanly on Windows and carries over unchanged to Postgres. Pair with OS disk encryption (BitLocker) for the DB file itself.
- **Uploads:** one PDF per upload in v1 (multi-month statements already cover history). Any upload can be deleted, removing exactly the rows it saved.

## 8. Build phases

Sequenced for implementation. Effort assumes solo, one bank first (SBI).

| Phase | What ships | Rough effort |
| --- | --- | --- |
| 1 — MVP spine | Auth + session, PDF upload + decrypt, extractor for the one bank, transactions table, Review screen with inline edit, normalise + rules categorisation, duplicate detection, Dashboard with daily/monthly/yearly | ~1.5–2 weeks |
| 2 — Real product | Subscription/recurring detection, budgets + history, category & top-merchant views, alerts, export, Transactions search/filter | ~2–3 weeks |
| 3 — Later | LLM categorisation fallback, learn-from-corrections, merchant icons, month-end forecast, a second bank | as needed |

**Ongoing:** per-bank parser maintenance (layouts change) and categorisation tuning — light once the dictionary has learned the user's regular merchants.

## 9. Build status (as of 2026-10-30)

Verified against a **synthetic** SBI statement only (`backend/samples/SBI_sample_locked.pdf`); balance check reconciles to ₹0.00. Some Phase-2/3 items were built early in the scaffold.

| Requirement | Phase | Status | Notes |
| --- | --- | --- | --- |
| Email/password login + session | 1 | ✅ Built | Single seeded user from `.env` |
| Google sign-in | 1 | ❌ Not built | |
| Upload + decrypt (password once, never stored) | 1 | ✅ Built | One file per upload (decided, §7). PDF or SBI's Excel download (.xlsx, .xls, or HTML/TSV saved as .xls; columns found by header name). Excel path untested against a real SBI file yet; password-protected Excel not supported |
| SBI extractor (table read + narration normaliser) | 1 | 🟡 Partial | Fitted to a real SBI statement (Jan 2026, masked): 57/57 rows, reconciles to ₹0.00 against the Statement Summary. That statement held only UPI rows; NEFT/IMPS/ATM/ACH/charges/interest in the real layout are still untested |
| Balance check | 1 | ✅ Built | |
| Review-before-save screen | 1 | ✅ Built | `/upload/preview` saves nothing and returns a signed, 1-hour token carrying the parsed rows; `/upload/commit` takes the token + per-merchant corrections. Duplicates shown greyed, uncategorised flagged |
| Rules + fuzzy categorisation | 1 | ✅ Built | ~45 seed merchants, `rapidfuzz` (88), then trade keywords ("MEDICALS" → Health, "KIRANA" → Groceries…). Most real UPI payees are local shops under a personal name, which no rule can know, so Review groups uncategorised payees for one-click categorising |
| Duplicate detection | 1 | ✅ Built | See duplicate key in §5 |
| Dashboard daily/monthly/yearly + KPIs, donut, top merchants | 1 | ✅ Built | |
| Transactions date-range + search + category filter | 2 | ✅ Built | |
| Learn from corrections (rule + retro-apply) | 3 | ✅ Built | From Review corrections and `PATCH /transactions/{id}/category`. A merchant-keyed rule overrides the narration-token match, so it also sticks for people, ATM and fees |
| Recurring detection | 2 | 🟡 Partial | 2+ months, ≤40% amount spread. Missing: next-charge date, price-increase flag, real cadence (always "Monthly"); `is_recurring` column never set |
| Budgets | 2 | ✅ Built | Per-month actuals (default: latest month with data), overall total, linear month-end projection for the current month |
| Alerts ("what Khaata noticed") | 2 | ❌ Not built | |
| Export (CSV / PDF) | 2 | ❌ Not built | |
| Stored data encrypted at rest | — | ❌ Not built | Approach decided (§7); plain SQLite today |
| LLM fallback, merchant icons, second bank | 3 | ❌ Not built | |
| Delete an upload and its rows | — | ✅ Built | `DELETE /uploads/{id}`; resets onboarding if no history is left |
| Automated tests | — | ✅ Started | `backend/tests/` — extractor, preview/commit, dedupe, corrections, delete, budgets (pytest, sample PDFs) |

**API surface today:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` · `POST /upload/preview`, `POST /upload/commit` · `GET /uploads`, `DELETE /uploads/{id}` · `GET /transactions`, `PATCH /transactions/{id}/category` · `GET /insights/overview?period=day|month|year`, `GET /insights/recurring` · `GET /budgets?month=YYYY-MM`, `PUT /budgets` · `GET /health`.

**Known issues**

- No migrations yet (tables come from `create_all`). Schema changes need the local `khaata.db` deleted; add Alembic before real data matters.
- Byte-identical transactions on the same day dedupe into one.
- Real SBI statements drop the `@handle` from UPI IDs, so person-vs-merchant is a guess: a 10-digit phone-number VPA is a person, anything else a merchant. Small payments to shopkeepers' phone-number VPAs land in Transfer · Person (excluded from spend) until recategorised.

**Open questions**

- None open. Resolved 2026-10-30: one file per upload; uploads are deletable; encryption approach in §7.
