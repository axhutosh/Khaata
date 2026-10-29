import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
    limit: int = 200,
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
    if q:
        like = f"%{q}%"
        query = query.filter(Transaction.merchant.ilike(like) | Transaction.raw_narration.ilike(like))
    rows = query.order_by(Transaction.txn_date.desc()).limit(limit).all()
    return [{
        "id": r.id, "date": r.txn_date.isoformat(), "merchant": r.merchant,
        "raw": r.raw_narration, "category": r.category, "method": r.method,
        "type": r.txn_type, "amount": float(r.amount), "kind": r.counterparty_kind,
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
