import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User


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
