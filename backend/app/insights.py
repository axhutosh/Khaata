"""Insight queries — every number is derived live from the transactions table.
Aggregates are computed, never stored as the source of truth.
"""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import Transaction

# categories that are not "spending"
NON_SPEND = {"Income", "Investments", "Transfer · Person", "Cashback"}


def _q(db: Session, user_id: str):
    return db.query(Transaction).filter(Transaction.user_id == user_id)


def overview(db: Session, user_id: str, period: str = "month") -> dict:
    """period: 'day' | 'month' | 'year'. Returns buckets + headline KPIs."""
    txns = _q(db, user_id).order_by(Transaction.txn_date).all()
    if not txns:
        return {"period": period, "buckets": [], "kpis": {}, "categories": [], "top_merchants": []}

    def key(d: dt.date) -> str:
        if period == "day":
            return d.isoformat()
        if period == "year":
            return str(d.year)
        return f"{d.year}-{d.month:02d}"

    income = defaultdict(Decimal)
    spend = defaultdict(Decimal)
    for t in txns:
        amt = Decimal(str(t.amount))
        if t.txn_type == "credit" and t.category == "Income":
            income[key(t.txn_date)] += amt
        elif t.txn_type == "debit" and t.category not in NON_SPEND:
            spend[key(t.txn_date)] += amt

    keys = sorted(set(list(income) + list(spend)))
    buckets = [{"label": k, "income": float(income[k]), "spend": float(spend[k])} for k in keys]

    total_income = float(sum(income.values()))
    total_spend = float(sum(spend.values()))
    saved = total_income - total_spend
    days = (txns[-1].txn_date - txns[0].txn_date).days + 1
    kpis = {
        "income": total_income,
        "spent": total_spend,
        "saved": saved,
        "savings_rate": round(saved / total_income * 100, 1) if total_income else 0,
        "daily_avg": round(total_spend / days, 0) if days else 0,
        "from": txns[0].txn_date.isoformat(),
        "to": txns[-1].txn_date.isoformat(),
    }
    return {
        "period": period, "buckets": buckets, "kpis": kpis,
        "categories": category_breakdown(db, user_id),
        "top_merchants": top_merchants(db, user_id),
    }


def category_breakdown(db: Session, user_id: str) -> list[dict]:
    rows = (_q(db, user_id)
            .filter(Transaction.txn_type == "debit", ~Transaction.category.in_(NON_SPEND))
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


def recurring(db: Session, user_id: str) -> list[dict]:
    """Merchants that appear in 2+ distinct months with a similar amount."""
    txns = _q(db, user_id).filter(Transaction.txn_type == "debit").all()
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_merchant[t.merchant].append(t)

    out = []
    for merchant, items in by_merchant.items():
        months = {(t.txn_date.year, t.txn_date.month) for t in items}
        if len(months) < 2:
            continue
        amounts = sorted(float(t.amount) for t in items)
        median = amounts[len(amounts) // 2]
        spread = (amounts[-1] - amounts[0]) / median if median else 1
        if spread > 0.4:          # amounts too varied -> not a clean subscription
            continue
        last = max(items, key=lambda t: t.txn_date)
        out.append({
            "merchant": merchant,
            "category": last.category,
            "amount": median,
            "cadence": "Monthly" if len(months) >= 2 else "—",
            "occurrences": len(items),
            "last_date": last.txn_date.isoformat(),
            "is_investment": last.category == "Investments",
        })
    return sorted(out, key=lambda r: r["amount"], reverse=True)


def budget_status(db: Session, user_id: str) -> list[dict]:
    from .models import Budget
    budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
    spent = {c["category"]: c["amount"] for c in category_breakdown(db, user_id)}
    out = []
    for b in budgets:
        used = spent.get(b.category, 0.0)
        limit = float(b.monthly_limit)
        out.append({
            "category": b.category, "limit": limit, "used": used,
            "pct": round(used / limit * 100) if limit else 0,
            "state": "over" if used > limit else ("near" if used > 0.9 * limit else "ok"),
        })
    return out
