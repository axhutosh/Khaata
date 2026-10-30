from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User
from ..auth import verify_password, current_user, login_user
from ..security import login_throttle, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)  # the ID token from Google's button


def _me(user: User) -> dict:
    return {"email": user.email, "onboarded": user.onboarded, "google": bool(user.google_sub)}


@router.get("/config")
def config():
    """Public: what the login page needs to render (no secrets)."""
    return {"google_client_id": settings.GOOGLE_CLIENT_ID or None}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email, ip = body.email.lower(), client_ip(request)
    login_throttle.check(ip, email)
    user = db.query(User).filter(User.email == email).first()
    if not verify_password(body.password, user.password_hash if user else None):
        login_throttle.fail(ip, email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    login_throttle.succeed(email)
    login_user(request, user)
    return _me(user)


def verify_google_token(credential: str) -> dict:
    """Check the ID token's signature, issuer, audience and expiry with Google's library."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    return id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID)


@router.post("/google")
def google(body: GoogleIn, request: Request, db: Session = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=404, detail="Google sign-in isn't configured.")
    ip = client_ip(request)
    login_throttle.check(ip, "google")
    try:
        claims = verify_google_token(body.credential)
    except ValueError:
        login_throttle.fail(ip, "google")
        raise HTTPException(status_code=401, detail="Google sign-in failed. Please try again.")

    email = (claims.get("email") or "").lower()
    if not claims.get("email_verified") or not email:
        raise HTTPException(status_code=403, detail="Your Google account's email isn't verified.")
    if email not in settings.ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="This Google account isn't allowed to use this Khaata.")

    user = db.query(User).filter(User.email == email).first()
    if user is None:  # an allow-listed email signing in for the first time
        user = User(email=email, password_hash="!google-only")
        db.add(user)
    if user.google_sub and user.google_sub != claims["sub"]:
        raise HTTPException(status_code=403, detail="This email is linked to a different Google account.")
    user.google_sub = claims["sub"]
    db.commit()
    login_user(request, user)
    return _me(user)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _me(user)
