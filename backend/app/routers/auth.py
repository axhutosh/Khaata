"""Email + password accounts: sign up, sign in, sign out. Anyone can create an account
(OPEN_SIGNUP) and gets their own, isolated Khaata; every query is scoped to it."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User
from ..auth import current_user, login_user
from .. import passwords
from ..passwords import hash_password, password_problem, verify_password
from ..security import client_ip, login_throttle, signup_throttle

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


def _me(user: User) -> dict:
    return {"email": user.email, "onboarded": user.onboarded}


@router.get("/config")
def config():
    """Public: what the sign-in page needs to know, including the new-password rules so the
    form checks exactly what the server will (frontend/src/passwordRules.js)."""
    return {
        "open_signup": settings.OPEN_SIGNUP,
        "password_policy": {"min_length": passwords.MIN_LENGTH, "passphrase_length": passwords.PASSPHRASE_LENGTH,
                            "max_length": passwords.MAX_LENGTH, "common": sorted(passwords.COMMON)},
    }


@router.post("/signup")
def signup(body: Credentials, request: Request, db: Session = Depends(get_db)):
    email, ip = body.email.lower(), client_ip(request)
    signup_throttle.check(ip, f"signup:{ip}")
    if not settings.may_sign_up(email):
        raise HTTPException(status_code=403, detail="New accounts are invite-only right now.")
    problem = password_problem(body.password, email)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    signup_throttle.fail(ip, f"signup:{ip}")  # counts every account made from this address
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    login_user(request, user)
    return _me(user)


@router.post("/login")
def login(body: Credentials, request: Request, db: Session = Depends(get_db)):
    email, ip = body.email.lower(), client_ip(request)
    login_throttle.check(ip, email)
    user = db.query(User).filter(User.email == email).first()
    if not verify_password(body.password, user.password_hash if user else None):
        login_throttle.fail(ip, email)
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    login_throttle.succeed(email)
    login_user(request, user)
    return _me(user)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _me(user)
