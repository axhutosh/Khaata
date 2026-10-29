"""Committed uploads: list them, or delete one along with the rows it saved."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Transaction, Upload
from ..auth import current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("")
def list_uploads(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Upload).filter(Upload.user_id == user.id)
            .order_by(Upload.created_at.desc()).all())
    return [{
        "id": u.id, "filename": u.filename, "created_at": u.created_at.isoformat(),
        "from": u.period_from.isoformat() if u.period_from else None,
        "to": u.period_to.isoformat() if u.period_to else None,
        "saved": u.saved, "duplicates": u.duplicates, "reconciles": u.reconciles,
    } for u in rows]


@router.delete("/{upload_id}")
def delete_upload(upload_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    upload = db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == user.id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    removed = db.query(Transaction).filter(
        Transaction.user_id == user.id, Transaction.upload_id == upload.id).delete()
    db.delete(upload)
    # with no history left, the next sign-in goes back through onboarding
    if not db.query(Transaction).filter(Transaction.user_id == user.id).first():
        user.onboarded = False
    db.commit()
    return {"ok": True, "removed": removed}
