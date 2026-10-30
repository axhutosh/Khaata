"""Insight queries — every number is derived live from the transactions table.
Aggregates are computed, never stored as the source of truth.
"""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from .models import Transaction
from . import recurring as rec

# categories that are not "spending"
NON_SPEND = {"Income", "Investments", "P2P Transfer", "Cashback"}


def _q(db: Session, user_id: str):
    return db.query(Transaction).filter(Transaction.user_id == user_id)


P2P = "P2P Transfer"
SMALL = 100  # rupees: a "small spend"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _in_order(db: Session, user_id: str) -> list[Transaction]:
    """Rows by date, and within a day in statement order (so running balances make sense)."""
    q = _q(db, user_id).order_by(Transaction.txn_date)
    if db.get_bind().dialect.name == "sqlite":
        q = q.order_by(text("transactions.rowid"))
    return q.all()


def _flow(t: Transaction) -> str:
    """Which bucket a payment out belongs to."""
    if t.category == P2P:
        return "people"
    if t.category == "Investments":
        return "investments"
    if t.category in ("Cash", "Bank Fees"):
        return "cash_fees"
    return "merchants"


def _money(n) -> str:
    return "₹" + f"{float(n):,.0f}"


def overview(db: Session, user_id: str, period: str = "month") -> dict:
    """period: 'day' | 'month' | 'year' sets the trend buckets; everything else covers all data."""
    txns = _in_order(db, user_id)
    if not txns:
        return {"period": period, "empty": True}

    def key(d: dt.date) -> str:
        if period == "day":
            return d.isoformat()
        if period == "year":
            return str(d.year)
        return f"{d.year}-{d.month:02d}"

    amt = {t.id: float(t.amount) for t in txns}
    debits = [t for t in txns if t.txn_type == "debit"]
    credits = [t for t in txns if t.txn_type == "credit"]
    spends = [t for t in debits if t.category not in NON_SPEND]

    b = defaultdict(lambda: defaultdict(float))
    for t in txns:
        row = b[key(t.txn_date)]
        if t.txn_type == "credit":
            row["money_in"] += amt[t.id]
        else:
            row["money_out"] += amt[t.id]
            row["spend" if t.category not in NON_SPEND else ("p2p" if t.category == P2P else "other")] += amt[t.id]
    buckets = [{"label": k, **{f: round(b[k][f], 2) for f in ("money_in", "money_out", "spend", "p2p", "other")}}
               for k in sorted(b)]

    out = defaultdict(float)
    for t in debits:
        out[_flow(t)] += amt[t.id]
    into = defaultdict(float)
    for t in credits:
        into["income" if t.category == "Income" else "people" if t.category == P2P else "other"] += amt[t.id]

    money_in, money_out, spent = (sum(amt[t.id] for t in xs) for xs in (credits, debits, spends))
    days = (txns[-1].txn_date - txns[0].txn_date).days + 1
    kpis = {
        "money_in": money_in, "money_out": money_out, "net": money_in - money_out,
        "spent": spent, "p2p_sent": out["people"], "p2p_received": into["people"],
        "invested": out["investments"], "income": into["income"],
        "savings_rate": round((into["income"] - spent) / into["income"] * 100, 1) if into["income"] else None,
        "daily_avg": round(spent / days, 0), "txn_count": len(txns), "days": days,
        "from": txns[0].txn_date.isoformat(), "to": txns[-1].txn_date.isoformat(),
    }

    # people you pay / who pay you
    people = defaultdict(lambda: {"sent": 0.0, "received": 0.0, "count": 0})
    for t in txns:
        if t.category == P2P:
            p = people[t.merchant]
            p["sent" if t.txn_type == "debit" else "received"] += amt[t.id]
            p["count"] += 1
    top_people = sorted(({"name": n, **v} for n, v in people.items()),
                        key=lambda p: p["sent"] + p["received"], reverse=True)[:8]

    weekday = [{"day": d, "amount": 0.0, "count": 0} for d in WEEKDAYS]
    for t in spends:
        w = weekday[t.txn_date.weekday()]
        w["amount"] += amt[t.id]
        w["count"] += 1

    small = [t for t in spends if amt[t.id] <= SMALL]
    small_spends = {"threshold": SMALL, "count": len(small), "total": sum(amt[t.id] for t in small),
                    "share": round(len(small) / len(spends) * 100) if spends else 0}

    closing = {}
    for t in txns:  # last row of each day is that day's closing balance
        closing[t.txn_date] = float(t.balance)
    balance = [{"date": d.isoformat(), "balance": v} for d, v in closing.items()]
    low = min(balance, key=lambda x: x["balance"])

    largest = [{"date": t.txn_date.isoformat(), "merchant": t.merchant, "amount": amt[t.id],
                "category": t.category} for t in sorted(spends, key=lambda t: -amt[t.id])[:5]]

    return {
        "period": period, "buckets": buckets, "kpis": kpis,
        "flows_out": [{"key": k, "amount": round(out[k], 2)} for k in ("merchants", "people", "investments", "cash_fees")],
        "flows_in": [{"key": k, "amount": round(into[k], 2)} for k in ("income", "people", "other")],
        "categories": category_breakdown(db, user_id),
        "top_merchants": top_merchants(db, user_id),
        "people": top_people, "weekday": weekday, "small_spends": small_spends,
        "balance": balance, "low_balance": low, "largest": largest,
        "noticed": _noticed(txns, spends, debits, amt, kpis, small_spends, low, weekday),
    }


def _noticed(txns, spends, debits, amt, kpis, small, low, weekday) -> list[dict]:
    """Plain-language observations, most useful first. tone: 'warn' | 'info' | 'good'."""
    notes = []
    if kpis["money_out"] and kpis["p2p_sent"]:
        n = sum(1 for t in debits if t.category == P2P)
        pct = round(kpis["p2p_sent"] / kpis["money_out"] * 100)
        notes.append({"tone": "info", "text": f"{pct}% of the money you sent out went to people: "
                      f"{_money(kpis['p2p_sent'])} across {n} UPI transfers."})
    if small["count"] >= 5:
        notes.append({"tone": "info", "text": f"{small['count']} payments of ₹{SMALL} or less added up to "
                      f"{_money(small['total'])} — {small['share']}% of everything you paid for."})
    if low["balance"] < 500:
        notes.append({"tone": "warn", "text": f"Your balance dipped to {_money(low['balance'])} on "
                      f"{dt.date.fromisoformat(low['date']):%d %b}."})
    if spends:
        big = max(spends, key=lambda t: amt[t.id])
        notes.append({"tone": "info", "text": f"Biggest single spend: {_money(amt[big.id])} at {big.merchant} "
                      f"on {big.txn_date:%d %b}."})
        values = sorted(amt[t.id] for t in spends)
        median = values[len(values) // 2]
        unusual = [t for t in spends if amt[t.id] > max(3 * median, 1000)]
        if unusual:
            notes.append({"tone": "warn", "text": f"{len(unusual)} payment{'s' if len(unusual) > 1 else ''} well above "
                          f"your usual (typical is {_money(median)}) — worth a look."})
    seen = defaultdict(int)
    for t in debits:
        if t.counterparty_kind == "merchant":
            seen[(t.merchant, t.txn_date, amt[t.id])] += 1
    dupes = [k for k, n in seen.items() if n > 1]
    if dupes:
        m, d, a = dupes[0]
        notes.append({"tone": "warn", "text": f"Possible double charge: {_money(a)} to {m} twice on {d:%d %b}."})
    fees = sum(amt[t.id] for t in debits if t.category == "Bank Fees")
    if fees:
        notes.append({"tone": "warn", "text": f"Bank charges came to {_money(fees)}."})
    busiest = max(weekday, key=lambda w: w["amount"])
    if busiest["amount"] and kpis["spent"]:
        notes.append({"tone": "info", "text": f"{busiest['day']} is your biggest spending day "
                      f"({round(busiest['amount'] / kpis['spent'] * 100)}% of spend)."})
    uncat = sum(amt[t.id] for t in spends if t.category == "Uncategorised")
    if kpis["spent"] and uncat / kpis["spent"] > 0.3:
        payees = len({t.merchant for t in spends if t.category == "Uncategorised"})
        notes.append({"tone": "info", "text": f"{_money(uncat)} of spending is still uncategorised "
                      f"({payees} payees). Categorise them in Transactions to sharpen these numbers."})
    if kpis["net"] > 0:
        notes.append({"tone": "good", "text": f"More came in than went out: you're up {_money(kpis['net'])} "
                      f"over these {kpis['days']} days."})
    return notes


def category_breakdown(db: Session, user_id: str,
                       start: dt.date | None = None, end: dt.date | None = None) -> list[dict]:
    q = _q(db, user_id)
    if start:
        q = q.filter(Transaction.txn_date >= start)
    if end:
        q = q.filter(Transaction.txn_date <= end)
    rows = (q.filter(Transaction.txn_type == "debit", ~Transaction.category.in_(NON_SPEND))
            .with_entities(Transaction.category, func.sum(Transaction.amount))
            .group_by(Transaction.category).all())
    rows = sorted(rows, key=lambda r: float(r[1]), reverse=True)
    return [{"category": c, "amount": float(a)} for c, a in rows]


def top_merchants(db: Session, user_id: str, limit: int = 8) -> list[dict]:
    rows = (_q(db, user_id)
            .filter(Transaction.txn_type == "debit", ~Transaction.category.in_(NON_SPEND))
            .with_entities(Transaction.merchant, func.sum(Transaction.amount), func.count())
            .group_by(Transaction.merchant).all())
    rows = sorted(rows, key=lambda r: float(r[1]), reverse=True)[:limit]
    return [{"merchant": m, "amount": float(a), "count": n} for m, a, n in rows]


def recurring(db: Session, user_id: str) -> dict:
    """Subscriptions, bills, SIPs/EMIs, regular transfers and income; see recurring.py."""
    return rec.detect(_q(db, user_id).all())


def _state(used: float, limit: float) -> str:
    return "over" if used > limit else ("near" if used > 0.9 * limit else "ok")


def budget_status(db: Session, user_id: str, month: str | None = None,
                  today: dt.date | None = None) -> dict:
    """Actual vs monthly limit for one calendar month ('YYYY-MM').
    Defaults to the latest month with transactions, since statements lag the calendar.
    Projection is linear for the current month; a past month projects to its actual."""
    from .models import Budget
    today = today or dt.date.today()
    if month:
        start = dt.date.fromisoformat(month + "-01")
    else:
        latest = _q(db, user_id).with_entities(func.max(Transaction.txn_date)).scalar()
        start = (latest or today).replace(day=1)
    end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)

    if start <= today <= end:
        scale = end.day / today.day
    else:
        scale = 1.0

    spent = {c["category"]: c["amount"] for c in category_breakdown(db, user_id, start, end)}
    items = []
    for b in db.query(Budget).filter(Budget.user_id == user_id).all():
        used, limit = spent.get(b.category, 0.0), float(b.monthly_limit)
        items.append({
            "category": b.category, "limit": limit, "used": used,
            "projected": round(used * scale, 2),
            "pct": round(used / limit * 100) if limit else 0,
            "state": _state(used, limit),
        })

    total_limit = sum(i["limit"] for i in items)
    total_used = sum(i["used"] for i in items)
    return {
        "month": f"{start.year}-{start.month:02d}",
        "items": items,
        "overall": {
            "limit": total_limit, "used": total_used,
            "projected": round(total_used * scale, 2),
            "state": _state(total_used, total_limit) if total_limit else "ok",
        },
    }
