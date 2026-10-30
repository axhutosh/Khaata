import re

import pytest
from fastapi.routing import APIRoute

from app import config, passwords
from app.main import app
from conftest import ACCOUNT_PASSWORD as PASSWORD, EMAIL, creds, preview

PUBLIC = {("POST", "/auth/signup"), ("POST", "/auth/login"), ("POST", "/auth/logout"),
          ("GET", "/auth/config"), ("GET", "/health")}


def _routes():
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in r.methods:
                yield m, r.path


def test_every_non_public_route_needs_a_session(anon):
    checked = 0
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        r = anon.request(method, re.sub(r"\{[^}]+\}", "x", path), json={})
        assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a session"
        checked += 1
    assert checked >= 12


def test_public_routes_are_exactly_these():
    assert {(m, p) for m, p in _routes() if (m, p) in PUBLIC} == PUBLIC


def test_no_google_sign_in_left():
    assert not any("google" in p for _, p in _routes())


# --- sign up --------------------------------------------------------------- #

def test_signup_creates_a_signed_in_account(anon):
    r = anon.post("/auth/signup", json=creds())
    assert r.status_code == 200 and r.json() == {"email": EMAIL, "onboarded": False}
    assert anon.get("/transactions").status_code == 200


def test_signup_twice_with_one_email_is_refused(anon):
    anon.post("/auth/signup", json=creds())
    assert anon.post("/auth/signup", json=creds(email=EMAIL.upper())).status_code == 409


@pytest.mark.parametrize("pw, why", [
    ("short", "at least"), ("password123", "easy to guess"), ("aaaaaaaaaaaa", "easy to guess"),
    ("my-own-phrase-x", None), ("x" * 129, "at most"),
])
def test_password_rules(pw, why):
    problem = passwords.password_problem(pw, "someone@x.in")
    assert (problem is None) if why is None else (why in problem)


def test_password_may_not_contain_the_email_name():
    assert "email" in passwords.password_problem("rameshkumar-rocks", "rameshkumar@x.in")


def test_weak_password_is_refused_at_signup(anon):
    r = anon.post("/auth/signup", json=creds(password="password123"))
    assert r.status_code == 422 and "guess" in r.json()["detail"]
    assert anon.get("/auth/me").status_code == 401


def test_invite_only_signup(anon, monkeypatch):
    monkeypatch.setattr(config.settings, "OPEN_SIGNUP", False)
    monkeypatch.setattr(config.settings, "ALLOWED_EMAILS", {"friend@x.in"})
    assert anon.post("/auth/signup", json=creds(email="stranger@x.in")).status_code == 403
    assert anon.post("/auth/signup", json=creds(email="friend@x.in")).status_code == 200


def test_signups_are_throttled_per_address(anon):
    for i in range(10):
        assert anon.post("/auth/signup", json=creds(email=f"u{i}@x.in")).status_code == 200
    assert anon.post("/auth/signup", json=creds(email="u99@x.in")).status_code == 429


# --- sign in --------------------------------------------------------------- #

def test_login_logout(anon):
    anon.post("/auth/signup", json=creds())
    anon.post("/auth/logout")
    assert anon.get("/auth/me").status_code == 401
    assert anon.post("/auth/login", json=creds(email="ME@Khaata.IN")).status_code == 200  # case-insensitive
    assert anon.get("/transactions").status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(anon):
    anon.post("/auth/signup", json=creds())
    anon.post("/auth/logout")
    a = anon.post("/auth/login", json=creds(password="wrong-password!"))
    b = anon.post("/auth/login", json=creds(email="nobody@khaata.in"))
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_is_throttled_after_repeated_failures(anon):
    anon.post("/auth/signup", json=creds())
    anon.post("/auth/logout")
    for _ in range(5):
        assert anon.post("/auth/login", json=creds(password="wrong-password!")).status_code == 401
    r = anon.post("/auth/login", json=creds())  # even the right one, for now
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_passwords_are_hashed_with_scrypt(anon):
    anon.post("/auth/signup", json=creds())
    from app.database import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        stored = db.query(User).one().password_hash
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert passwords.verify_password(PASSWORD, stored) and not passwords.verify_password("nope", stored)
    assert not passwords.verify_password(PASSWORD, "!google-only")  # legacy unusable hash never matches


def test_logout_ends_the_session(client):
    assert client.get("/auth/me").status_code == 200
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/transactions").status_code == 401


# --- request-level protections --------------------------------------------- #

def test_cross_site_writes_are_blocked(client):
    evil = {"Origin": "https://evil.example"}
    assert client.post("/transactions/reclassify", headers=evil).status_code == 403
    assert client.post("/auth/logout", headers=evil).status_code == 403
    assert client.post("/auth/login", headers=evil, json=creds()).status_code == 403
    assert client.get("/auth/me").status_code == 200  # session survived
    assert client.post("/transactions/reclassify", headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_security_headers(client):
    h = client.get("/transactions").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store"
    assert "default-src 'none'" in h["content-security-policy"]


def test_session_cookie_is_httponly(anon):
    cookie = anon.post("/auth/signup", json=creds()).headers["set-cookie"].lower()
    assert "khaata_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_oversized_upload_is_refused(client, monkeypatch):
    monkeypatch.setattr(config.settings, "MAX_UPLOAD_MB", 0)
    assert preview(client).status_code == 413


def test_production_refuses_unsafe_defaults(monkeypatch):
    s = config.Settings()
    monkeypatch.setattr(s, "ENV", "production")
    monkeypatch.setattr(s, "SECRET_KEY", "change-this-to-a-long-random-string")
    monkeypatch.setattr(s, "SESSION_SECURE", True)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.check()
    monkeypatch.setattr(s, "SECRET_KEY", "k" * 48)
    s.check()  # all good: no error
