from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from passlib.hash import pbkdf2_sha256
from .database import get_db
from .models import User


def hash_password(pw: str) -> str:
    return pbkdf2_sha256.hash(pw)


def verify_password(pw: str, h: str) -> bool:
    return pbkdf2_sha256.verify(pw, h)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalid")
    return user
