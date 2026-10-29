"""Upload endpoint: decrypt -> parse -> balance check -> dedupe -> save.

Two-step flow so the UI can ask for a password only when needed:
  POST /upload/preview  -> parse and return rows + balance check (nothing saved)
  POST /upload/commit   -> save the reviewed rows
For the scaffold, /upload does both in one call; split later if you want the
explicit Review step to gate the save.
"""
import hashlib
from decimal import Decimal
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Transaction, MerchantRule
from ..auth import current_user
from .. import extractor

router = APIRouter(prefix="/upload", tags=["upload"])


def _user_rules(db: Session, user_id: str) -> dict:
    rules = dict(extractor.SEED_RULES)
    for r in db.query(MerchantRule).filter(MerchantRule.user_id == user_id).all():
        rules[r.token] = (r.merchant, r.category)
    return rules


def _hash(user_id: str, t) -> str:
    raw = f"{user_id}|{t.txn_date}|{t.amount}|{t.txn_type}|{t.raw_narration}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


@router.post("")
async def upload(
    file: UploadFile = File(...),
    password: str | None = Form(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()

    if extractor.is_encrypted(data) and not password:
        raise HTTPException(status_code=422, detail="PDF is password protected. Provide the password.")
    try:
        pdf_bytes = extractor.decrypt_to_bytes(data, password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    rules = _user_rules(db, user.id)
    parsed = extractor.parse(pdf_bytes, rules)
    if not parsed:
        raise HTTPException(status_code=422, detail="No transactions found. Is this an SBI statement?")

    opening = extractor.extract_opening(pdf_bytes) or (parsed[0].balance - (
        parsed[0].amount if parsed[0].txn_type == "credit" else -parsed[0].amount))
    check = extractor.balance_check(parsed, Decimal(str(opening)))

    saved, duplicates = 0, 0
    for t in parsed:
        h = _hash(user.id, t)
        exists = db.query(Transaction).filter(
            Transaction.user_id == user.id, Transaction.txn_hash == h).first()
        if exists:
            duplicates += 1
            continue
        db.add(Transaction(
            user_id=user.id, txn_date=t.txn_date, amount=t.amount, txn_type=t.txn_type,
            balance=t.balance, raw_narration=t.raw_narration, merchant=t.merchant,
            category=t.category, method=t.method, counterparty_kind=t.counterparty_kind,
            source_file=file.filename, txn_hash=h,
        ))
        saved += 1

    if not user.onboarded:
        user.onboarded = True
    db.commit()

    return {
        "saved": saved, "duplicates": duplicates, "parsed": len(parsed),
        "balance_check": check,
        "rows": [t.as_dict() for t in parsed],
    }
