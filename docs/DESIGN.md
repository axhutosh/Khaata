# Khaata — Design spec

The approved UI. The live design canvas (six artboards, clickable) is at:
https://claude.ai/artifact/TBBxMLxgRfkzeTXZtdAWLo

The React frontend in `frontend/` already implements this design system. This file
is the written reference so any session can match it without opening the canvas.

## Design direction

A calm "digital ledger" look: warm off-white ground, near-black ink, a single deep-jade
accent for money/trust (not the clichéd finance green), tabular figures for precision,
and a fixed categorical palette for all charts so a colour means the same thing everywhere.
India-first throughout (₹, Indian merchants).

## Design tokens

Defined in `frontend/src/styles.css` as CSS variables.

| Token | Value | Use |
| --- | --- | --- |
| `--ground` | `#F7F6F2` | Page background |
| `--surface` | `#FFFFFF` | Cards |
| `--ink` | `#16181D` | Primary text |
| `--muted` | `#5B6068` | Secondary text |
| `--faint` | `#8A9099` | Labels, hints |
| `--line` | `#E6E4DE` | Borders, hairlines |
| `--accent` | `#0E7C66` | Primary / money / positive (jade) |
| `--accent-dark` | `#0A5F4E` | Hover / emphasis |
| `--spend` | `#C2410C` | Spend / negative / over-budget |

**Category palette** (used in charts; keep stable):

| Category | Colour |
| --- | --- |
| Food & Dining | `#E2663B` |
| Shopping | `#3B6FE2` |
| Bills & Utilities | `#0E9488` |
| Groceries | `#4F9D3A` |
| Entertainment | `#D4477E` |
| Transport | `#7C4DE2` |
| Insurance | `#B08A2E` |
| Transfers / Cash | `#8A9099` |
| Uncategorised | `#B0B4BB` |

**Type:** `Space Grotesk` (600) for headings and all figures; `Inter` for body/UI.
Numbers use tabular figures (`font-variant-numeric: tabular-nums`).

**Shape:** cards radius 16px; inputs/buttons radius 10px; pills 999px. Touch targets ≥ 44px.

## Screens

Six screens. The first three are the one-time onboarding flow; the last three are the product.

1. **Login** — split layout. Dark value panel on the left (brand + three promises: reads
   locked PDFs, daily/monthly/yearly insights, password never stored); sign-in form on the
   right (email + password, Google button). First-run → Upload; returning → Dashboard.

2. **Upload & Unlock** — centered card. File detected as encrypted → password field with a
   bank-specific hint ("PAN in capitals, or name + DOB"); "Unlock & scan" action; note that
   the password is used once then discarded. A step rail shows Upload → Unlock → Review → Insights.

3. **Review** — the trust step. A green **balance-check banner** (opening + credits − debits
   = closing). A table: Date · Merchant (with the raw narration shown faint underneath) ·
   Category (editable; uncategorised rows flagged amber) · Amount. Person-vs-merchant is
   distinguished. "Looks good — save" commits.

4. **Dashboard** — the product home. App shell with sidebar (Dashboard, Transactions,
   Subscriptions, Budgets + an Upload button). Daily/Monthly/Yearly toggle. Four KPIs
   (Income, Spent, Saved, savings rate / daily avg). Income-vs-spend bar chart. Category
   donut. Top-merchants bars. An alerts panel ("what Khaata noticed").

5. **Subscriptions** — auto-detected recurring payments: merchant, cadence, next-charge date,
   amount. Price-increase flag (e.g. "↑ ₹150"). SIPs tagged "Wealth, not spend".

6. **Budgets** — overall budget vs actual + a month-end projection line, then per-category
   progress bars with over (orange) / near (amber) / on-track (jade) states.

## Rules for building UI here

- Numbers always tabular; currency via the `inr()` helper (`₹` + en-IN grouping, no decimals in summaries).
- Never carry colour meaning by hue alone — over-budget is also darker/orange, not just "red".
- Charts use the category palette above; the accent jade is income/positive, `--spend` orange is spending.
- Keep the shell, card, pill and button classes from `styles.css` rather than re-styling per page.
