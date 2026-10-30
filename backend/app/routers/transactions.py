import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Transaction
from ..auth import current_user
from .. import rules

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_txns(
    start: dt.date | None = None,
    end: dt.date | None = None,
    category: str | None = None,
    q: str | None = None,
    type: str | None = Query(None, pattern="^(debit|credit)$"),
    kind: str | None = Query(None, pattern="^(person|merchant|self|bank)$"),
    limit: int = Query(200, ge=1, le=10000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(Transaction.user_id == user.id)
    if start:
        query = query.filter(Transaction.txn_date >= start)
    if end:
        query = query.filter(Transaction.txn_date <= end)
    if category:
        query = query.filter(Transaction.category == category)
    if type:
        query = query.filter(Transaction.txn_type == type)
    if kind:
        query = query.filter(Transaction.counterparty_kind == kind)
    # newest first; within a day, latest statement row first (so balances read top-down)
    query = query.order_by(Transaction.txn_date.desc())
    if db.get_bind().dialect.name == "sqlite":
        query = query.order_by(text("transactions.rowid DESC"))
    if q:  # narrations are encrypted, so match after decrypting (fine at one person's volume)
        needle = q.lower()
        rows = [r for r in query.all() if needle in r.merchant.lower() or needle in r.raw_narration.lower()][:limit]
    else:
        rows = query.limit(limit).all()
    return [{
        "id": r.id, "date": r.txn_date.isoformat(), "merchant": r.merchant,
        "raw": r.raw_narration, "category": r.category, "method": r.method,
        "type": r.txn_type, "amount": float(r.amount), "kind": r.counterparty_kind,
        "balance": float(r.balance), "source": r.source_file,
    } for r in rows]


class Recategorize(BaseModel):
    category: str
    apply_to_similar: bool = True   # save a rule + update matching rows


@router.patch("/{txn_id}/category")
def recategorize(txn_id: str, body: Recategorize,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(
        Transaction.id == txn_id, Transaction.user_id == user.id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    txn.category = body.category

    if body.apply_to_similar:
        rules.learn(db, user.id, txn.merchant, body.category)

    db.commit()
    return {"ok": True}


@router.post("/reclassify")
def reclassify(user: User = Depends(current_user), db: Session = Depends(get_db)):
    changed = rules.reclassify(db, user.id)
    db.commit()
    return {"changed": changed}
