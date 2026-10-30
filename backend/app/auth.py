import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from passlib.hash import pbkdf2_sha256
from .database import get_db
from .models import User

# compared against when the email doesn't exist, so a wrong email costs the same time
# as a wrong password and response timing doesn't reveal which accounts exist
_DUMMY_HASH = pbkdf2_sha256.hash("not-a-real-password")


def hash_password(pw: str) -> str:
    return pbkdf2_sha256.hash(pw)


def verify_password(pw: str, h: str | None) -> bool:
    try:
        return pbkdf2_sha256.verify(pw, h or _DUMMY_HASH) and h is not None
    except (ValueError, TypeError):  # unusable hash, e.g. a Google-only account
        return False


def login_user(request: Request, user: User) -> None:
    """Start a fresh session for this user (dropping anything from before sign-in)."""
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["auth_at"] = int(time.time())


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = db.get(User, uid)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session invalid")
    return user
