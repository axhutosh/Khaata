import re

import pytest
from fastapi.routing import APIRoute

from app import config
from app.main import app
from app.routers import auth as auth_router
from conftest import google_token, preview

PUBLIC = {("POST", "/auth/logout"), ("GET", "/auth/config"), ("POST", "/auth/google"), ("GET", "/health")}


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
        url = re.sub(r"\{[^}]+\}", "x", path)
        r = anon.request(method, url, json={})
        assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a session"
        checked += 1
    assert checked >= 12


def test_public_routes_are_exactly_these():
    assert {(m, p) for m, p in _routes() if (m, p) in PUBLIC} == PUBLIC


def test_there_is_no_password_sign_in(anon):
    assert ("POST", "/auth/login") not in set(_routes())
    assert anon.post("/auth/login", json={"email": "me@khaata.in", "password": "x"}).status_code in (404, 405)


def test_logout_ends_the_session(client):
    assert client.get("/auth/me").status_code == 200
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/transactions").status_code == 401


def test_cross_site_writes_are_blocked(client):
    evil = {"Origin": "https://evil.example"}
    assert client.post("/transactions/reclassify", headers=evil).status_code == 403
    assert client.post("/auth/logout", headers=evil).status_code == 403
    assert client.post("/auth/google", headers=evil, json={"credential": google_token()}).status_code == 403
    assert client.get("/auth/me").status_code == 200  # session survived
    assert client.post("/transactions/reclassify", headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_security_headers(client):
    h = client.get("/transactions").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store"
    assert "default-src 'none'" in h["content-security-policy"]


def test_session_cookie_is_httponly(anon):
    r = anon.post("/auth/google", json={"credential": google_token()})
    cookie = r.headers["set-cookie"].lower()
    assert "khaata_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_oversized_upload_is_refused(client, monkeypatch):
    monkeypatch.setattr(config.settings, "MAX_UPLOAD_MB", 0)
    assert preview(client).status_code == 413


# --- Google sign-in -------------------------------------------------------- #

def test_google_not_configured_is_404(anon, monkeypatch):
    monkeypatch.setattr(config.settings, "GOOGLE_CLIENT_ID", "")
    assert anon.get("/auth/config").json() == {"google_client_id": None}
    assert anon.post("/auth/google", json={"credential": google_token()}).status_code == 404


def test_google_sign_in_links_the_account(anon):
    assert anon.get("/auth/config").json()["google_client_id"].endswith(".apps.googleusercontent.com")
    r = anon.post("/auth/google", json={"credential": google_token()})
    assert r.status_code == 200 and r.json() == {"email": "me@khaata.in", "onboarded": False, "google": True}
    assert anon.get("/transactions").status_code == 200


def test_google_email_is_case_insensitive(anon):
    assert anon.post("/auth/google", json={"credential": google_token(email="ME@Khaata.in")}).status_code == 200


def test_open_signup_lets_any_verified_google_account_in(anon):
    r = anon.post("/auth/google", json={"credential": google_token(email="stranger@gmail.com", sub="s-1")})
    assert r.status_code == 200 and r.json()["email"] == "stranger@gmail.com" and r.json()["onboarded"] is False


def test_invite_only_rejects_other_emails(anon, monkeypatch):
    monkeypatch.setattr(config.settings, "OPEN_SIGNUP", False)
    assert anon.post("/auth/google", json={"credential": google_token(email="stranger@gmail.com")}).status_code == 403
    assert anon.get("/auth/me").status_code == 401
    assert anon.post("/auth/google", json={"credential": google_token()}).status_code == 200  # listed: fine


def test_google_rejects_unverified_email(anon):
    assert anon.post("/auth/google", json={"credential": google_token(verified=False)}).status_code == 403


def test_google_rejects_a_different_google_account_for_the_same_email(anon):
    assert anon.post("/auth/google", json={"credential": google_token(sub="first")}).status_code == 200
    anon.post("/auth/logout")
    assert anon.post("/auth/google", json={"credential": google_token(sub="someone-else")}).status_code == 403


def test_google_bad_token_is_401_and_throttled(anon, monkeypatch):
    def bad(_):
        raise ValueError("Token expired")
    monkeypatch.setattr(auth_router, "verify_google_token", bad)
    for _ in range(5):  # 5 failures from one address
        assert anon.post("/auth/google", json={"credential": google_token()}).status_code == 401
    r = anon.post("/auth/google", json={"credential": google_token()})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_seed_account_has_no_usable_password(anon):
    from app.database import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        assert {u.password_hash for u in db.query(User).all()} == {auth_router.NO_PASSWORD}


def test_production_refuses_unsafe_defaults(monkeypatch):
    s = config.Settings()
    monkeypatch.setattr(s, "ENV", "production")
    monkeypatch.setattr(s, "SECRET_KEY", "change-this-to-a-long-random-string")
    monkeypatch.setattr(s, "GOOGLE_CLIENT_ID", "x.apps.googleusercontent.com")
    monkeypatch.setattr(s, "SESSION_SECURE", True)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.check()
    monkeypatch.setattr(s, "SECRET_KEY", "k" * 48)
    monkeypatch.setattr(s, "GOOGLE_CLIENT_ID", "")
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        s.check()
    monkeypatch.setattr(s, "GOOGLE_CLIENT_ID", "x.apps.googleusercontent.com")
    s.check()  # all good: no error
