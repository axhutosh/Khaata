"""Upload endpoints: decrypt -> parse -> balance check -> review -> dedupe -> save.

  POST /upload/preview  -> parse and return rows + balance check. Saves nothing.
                           Returns a signed token carrying the parsed rows, so the
                           PDF and password can be discarded immediately.
  POST /upload/commit   -> token + the user's category corrections -> save.
"""
import hashlib
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User, Transaction, Upload
from ..auth import current_user
from .. import extractor, rules

router = APIRouter(prefix="/upload", tags=["upload"])

_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="upload-preview")
PREVIEW_TTL = 60 * 60  # seconds a preview stays committable


def _hash(user_id: str, t) -> str:
    raw = f"{user_id}|{t.txn_date}|{t.amount}|{t.txn_type}|{t.raw_narration}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _saved_hashes(db: Session, user_id: str, hashes: list[str]) -> set[str]:
    rows = db.query(Transaction.txn_hash).filter(
        Transaction.user_id == user_id, Transaction.txn_hash.in_(hashes)).all()
    return {h for (h,) in rows}


@router.post("/preview")
async def preview(
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
        status = 401 if "password" in str(e) else 422
        raise HTTPException(status_code=status, detail=str(e))

    layout = extractor.read_pdf(pdf_bytes)
    parsed = extractor.parse_tables(layout.tables, rules.user_rules(db, user.id))
    if not parsed:
        raise HTTPException(status_code=422, detail="No transactions found. Is this an SBI statement?")

    summary = extractor.statement_summary(layout.text)
    opening = summary["opening"]
    if opening is None:
        opening = extractor.opening_from_first_row(parsed)
    check = extractor.balance_check(parsed, opening, summary["closing"])

    hashes = [_hash(user.id, t) for t in parsed]
    saved, seen, rows = _saved_hashes(db, user.id, hashes), set(), []
    for t, h in zip(parsed, hashes):
        rows.append({**t.as_dict(), "duplicate": h in saved or h in seen})
        seen.add(h)

    token = _signer.dumps({
        "user_id": user.id, "filename": file.filename,
        "rows": [t.as_dict() for t in parsed], "reconciles": check["reconciles"],
    })
    return {
        "token": token, "filename": file.filename, "balance_check": check,
        "rows": rows, "parsed": len(rows), "duplicates": sum(r["duplicate"] for r in rows),
        "categories": extractor.CATEGORIES,
    }


class CommitIn(BaseModel):
    token: str
    corrections: dict[str, str] = {}   # merchant -> corrected category


@router.post("/commit")
def commit(body: CommitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        payload = _signer.loads(body.token, max_age=PREVIEW_TTL)
    except SignatureExpired:
        raise HTTPException(status_code=410, detail="This preview expired. Upload the statement again.")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid preview token.")
    if payload["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="This preview belongs to another user.")

    parsed = [extractor.ParsedTxn.from_dict(d) for d in payload["rows"]]
    merchants = {t.merchant for t in parsed}
    for merchant, category in body.corrections.items():
        if merchant not in merchants or not category.strip():
            raise HTTPException(status_code=422, detail=f"Bad correction for {merchant!r}.")
    for t in parsed:
        if t.merchant in body.corrections:
            t.category = body.corrections[t.merchant].strip()

    upload = Upload(user_id=user.id, filename=payload["filename"], reconciles=payload["reconciles"],
                    period_from=min(t.txn_date for t in parsed),
                    period_to=max(t.txn_date for t in parsed))
    db.add(upload)
    db.flush()

    hashes = [_hash(user.id, t) for t in parsed]
    skip = _saved_hashes(db, user.id, hashes)
    for t, h in zip(parsed, hashes):
        if h in skip:
            upload.duplicates += 1
            continue
        skip.add(h)
        db.add(Transaction(
            user_id=user.id, txn_date=t.txn_date, amount=t.amount, txn_type=t.txn_type,
            balance=t.balance, raw_narration=t.raw_narration, merchant=t.merchant,
            category=t.category, method=t.method, counterparty_kind=t.counterparty_kind,
            upload_id=upload.id, source_file=upload.filename, txn_hash=h,
        ))
        upload.saved += 1
    db.flush()

    # corrections become rules for future uploads and retro-apply to older rows
    for merchant, category in body.corrections.items():
        rules.learn(db, user.id, merchant, category.strip())

    user.onboarded = True
    db.commit()
    return {"upload_id": upload.id, "saved": upload.saved, "duplicates": upload.duplicates}
