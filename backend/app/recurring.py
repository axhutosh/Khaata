"""Recurring payments: subscriptions, bills, SIPs/EMIs, regular transfers and regular income.

A group (same merchant, same direction) is recurring when its payments are evenly spaced
at a known cadence AND similar in size. One sighting isn't a pattern, except for services
that only ever bill on a schedule (Netflix, a SIP, an ACH mandate) - those are flagged as
"likely" so a one-month upload still shows something useful, and confirmed once a second
month arrives. Everything is relative to the latest date in the data, not today, because
statements lag the calendar.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from statistics import median

P2P = "P2P Transfer"

# name, typical days, accepted gap range
CADENCES = [
    ("Weekly", 7, (5, 9)),
    ("Fortnightly", 14, (12, 17)),
    ("Monthly", 30, (26, 35)),
    ("Quarterly", 91, (84, 98)),
    ("Yearly", 365, (350, 380)),
]

# services that bill on a schedule by nature: one payment is enough to call them recurring
SCHEDULED = {
    "netflix", "spotify", "disney+ hotstar", "hotstar", "youtube", "amazon prime", "prime video",
    "apple", "google", "jio", "airtel", "bsnl", "vi", "tata play", "lic", "hdfc life", "groww sip",
    "zerodha", "upstox", "cred",
}
SCHEDULED_CATEGORIES = {"Investments", "Insurance"}
LOAN_WORDS = ("emi", "loan", "finance", "bajaj fin", "home credit", "capital")


def _kind_of(merchant: str, category: str, method: str, txn_type: str) -> str:
    m = merchant.lower()
    if txn_type == "credit":
        return "income"
    if category == "Investments":
        return "investment"
    if category == "Insurance":
        return "insurance"
    if any(w in m for w in LOAN_WORDS) or (method == "ACH" and category in ("Bills & Utilities", "Uncategorised")):
        return "emi"
    if category == P2P:
        return "transfer"
    if category == "Bills & Utilities":
        return "bill"
    if category == "Entertainment" or m in SCHEDULED:
        return "subscription"
    return "regular"


def _cadence(gaps: list[int]):
    """The cadence most gaps fit (>= 70% of them), or None."""
    if not gaps:
        return None
    for name, days, (lo, hi) in CADENCES:
        fit = sum(lo <= g <= hi for g in gaps)
        if fit / len(gaps) >= 0.7:
            return name, days
    return None


def _stable(amounts: list[float]) -> bool:
    """Similar amounts: most within 15% of the median, or all within ~35% of each other
    (a subscription with one price rise is still that subscription)."""
    mid = median(amounts)
    if mid <= 0:
        return False
    close = sum(abs(a - mid) <= 0.15 * mid for a in amounts) / len(amounts) >= 0.7
    return close or max(amounts) / max(min(amounts), 0.01) <= 1.35


def _status(next_date: dt.date, days: int, as_of: dt.date) -> str:
    grace = max(3, round(days * 0.25))
    if as_of > next_date + dt.timedelta(days=grace):
        return "stopped"
    if (next_date - as_of).days <= 7:
        return "due_soon"
    return "active"


def detect(txns: list, as_of: dt.date | None = None) -> dict:
    """txns: objects with merchant, category, method, txn_type, txn_date, amount."""
    if not txns:
        return {"as_of": None, "months_covered": 0, "items": [], "frequent": [], "totals": {}}
    as_of = as_of or max(t.txn_date for t in txns)
    first = min(t.txn_date for t in txns)
    months = len({(t.txn_date.year, t.txn_date.month) for t in txns})

    groups = defaultdict(list)
    for t in txns:
        groups[(t.merchant, t.txn_type)].append(t)

    items, frequent = [], []
    for (merchant, txn_type), rows in groups.items():
        rows.sort(key=lambda t: t.txn_date)
        # several payments on one day count once for spacing (split bills, retries)
        by_day = defaultdict(float)
        for t in rows:
            by_day[t.txn_date] += float(t.amount)
        days_ = sorted(by_day)
        amounts = [by_day[d] for d in days_]
        gaps = [(b - a).days for a, b in zip(days_, days_[1:])]
        last = rows[-1]
        kind = _kind_of(merchant, last.category, last.method, txn_type)

        cad = _cadence(gaps) if len(days_) >= 2 else None
        confidence, reason = None, ""
        if cad and _stable(amounts):
            confidence = "high" if len(days_) >= 3 else "medium"
            reason = f"{len(days_)} payments about {cad[1]} days apart, similar amounts"
        elif len(days_) <= 2 and txn_type == "debit" and (
                merchant.lower() in SCHEDULED or last.category in SCHEDULED_CATEGORIES or last.method == "ACH"):
            cad = ("Monthly", 30)
            confidence = "likely"
            reason = ("auto-debit mandate" if last.method == "ACH"
                      else f"{merchant} usually bills monthly" if merchant.lower() in SCHEDULED
                      else f"{last.category.lower()} payments are usually scheduled")
            reason += "; seen once so far" if len(days_) == 1 else "; upload more months to confirm"

        if confidence:
            name, cad_days = cad
            interval = round(median(gaps)) if gaps and confidence != "likely" else cad_days
            next_date = days_[-1] + dt.timedelta(days=interval)
            change = None
            if len(amounts) >= 2 and abs(amounts[-1] - amounts[-2]) > max(1, 0.02 * amounts[-2]):
                change = {"from": amounts[-2], "to": amounts[-1], "diff": round(amounts[-1] - amounts[-2], 2)}
            items.append({
                "merchant": merchant, "category": last.category, "kind": kind,
                "direction": "in" if txn_type == "credit" else "out",
                "cadence": name, "interval_days": interval,
                "amount": amounts[-1], "typical": round(median(amounts), 2),
                "monthly": round(amounts[-1] * 30 / interval, 2),
                "occurrences": len(rows), "first_date": days_[0].isoformat(), "last_date": days_[-1].isoformat(),
                "next_date": next_date.isoformat(), "status": _status(next_date, interval, as_of),
                "price_change": change, "confidence": confidence, "reason": reason,
                "history": [{"date": d.isoformat(), "amount": by_day[d]} for d in days_],
            })
        elif txn_type == "debit" and len(rows) >= 4 and last.category != P2P:
            span_weeks = max(1, ((as_of - first).days + 1) / 7)
            total = sum(float(t.amount) for t in rows)
            frequent.append({
                "merchant": merchant, "category": last.category, "count": len(rows),
                "total": round(total, 2), "average": round(total / len(rows), 2),
                "per_week": round(len(rows) / span_weeks, 1), "last_date": days_[-1].isoformat(),
            })

    order = {"subscription": 0, "bill": 1, "emi": 2, "insurance": 3, "investment": 4, "regular": 5,
             "transfer": 6, "income": 7}
    items.sort(key=lambda i: (order[i["kind"]], -i["monthly"]))
    frequent.sort(key=lambda f: -f["total"])

    def monthly(*kinds):
        return round(sum(i["monthly"] for i in items if i["kind"] in kinds and i["status"] != "stopped"), 2)

    return {
        "as_of": as_of.isoformat(), "months_covered": months, "items": items, "frequent": frequent[:8],
        "totals": {
            "subscriptions": monthly("subscription", "bill", "emi", "insurance", "regular"),
            "investments": monthly("investment"),
            "transfers": monthly("transfer"),
            "income": monthly("income"),
            "count": sum(1 for i in items if i["status"] != "stopped"),
            "price_rises": sum(1 for i in items if i["price_change"] and i["price_change"]["diff"] > 0),
        },
    }
