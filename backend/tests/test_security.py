import re

import pytest
from fastapi.routing import APIRoute

from app import config
from app.main import app
from app.routers import auth as auth_router
from conftest import preview

PUBLIC = {("POST", "/auth/login"), ("POST", "/auth/logout"), ("GET", "/auth/config"),
          ("POST", "/auth/google"), ("GET", "/health")}


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


def test_logout_ends_the_session(client):
    assert client.get("/auth/me").status_code == 200
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/transactions").status_code == 401


def test_wrong_password_and_unknown_email_look_the_same(anon):
    a = anon.post("/auth/login", json={"email": "me@khaata.in", "password": "nope"})
    b = anon.post("/auth/login", json={"email": "nobody@khaata.in", "password": "nope"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_is_throttled_after_repeated_failures(anon):
    for _ in range(5):
        assert anon.post("/auth/login", json={"email": "me@khaata.in", "password": "bad"}).status_code == 401
    r = anon.post("/auth/login", json={"email": "me@khaata.in", "password": "pw"})  # even the right one
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_email_is_case_insensitive(anon):
    assert anon.post("/auth/login", json={"email": "ME@Khaata.in", "password": "pw"}).status_code == 200


def test_cross_site_writes_are_blocked(client):
    evil = {"Origin": "https://evil.example"}
    assert client.post("/transactions/reclassify", headers=evil).status_code == 403
    assert client.post("/auth/logout", headers=evil).status_code == 403
    assert client.get("/auth/me").status_code == 200  # session survived
    ok = {"Origin": "http://localhost:5173"}
    assert client.post("/transactions/reclassify", headers=ok).status_code == 200


def test_security_headers(client):
    h = client.get("/transactions").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store"
    assert "default-src 'none'" in h["content-security-policy"]


def test_session_cookie_is_httponly(anon):
    r = anon.post("/auth/login", json={"email": "me@khaata.in", "password": "pw"})
    cookie = r.headers["set-cookie"].lower()
    assert "khaata_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_oversized_upload_is_refused(client, monkeypatch):
    monkeypatch.setattr(config.settings, "MAX_UPLOAD_MB", 0)
    assert preview(client).status_code == 413


# --- Google sign-in -------------------------------------------------------- #

@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(config.settings, "GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(config.settings, "ALLOWED_EMAILS", {"me@khaata.in"})
    claims = {"sub": "google-123", "email": "me@khaata.in", "email_verified": True}
    monkeypatch.setattr(auth_router, "verify_google_token", lambda cred: dict(claims))
    return claims


TOKEN = {"credential": "x" * 40}


def test_google_not_configured_is_404(anon, monkeypatch):
    monkeypatch.setattr(config.settings, "GOOGLE_CLIENT_ID", "")
    assert anon.get("/auth/config").json() == {"google_client_id": None}
    assert anon.post("/auth/google", json=TOKEN).status_code == 404


def test_google_sign_in_links_the_account(anon, google):
    assert anon.get("/auth/config").json()["google_client_id"].endswith(".apps.googleusercontent.com")
    r = anon.post("/auth/google", json=TOKEN)
    assert r.status_code == 200 and r.json()["google"] is True
    assert anon.get("/transactions").status_code == 200


def test_google_rejects_other_emails(anon, google):
    google["email"] = "stranger@gmail.com"
    assert anon.post("/auth/google", json=TOKEN).status_code == 403
    assert anon.get("/auth/me").status_code == 401


def test_google_rejects_unverified_email(anon, google):
    google["email_verified"] = False
    assert anon.post("/auth/google", json=TOKEN).status_code == 403


def test_google_rejects_a_different_google_account_for_the_same_email(anon, google):
    assert anon.post("/auth/google", json=TOKEN).status_code == 200
    anon.post("/auth/logout")
    google["sub"] = "someone-else"
    assert anon.post("/auth/google", json=TOKEN).status_code == 403


def test_google_bad_token_is_401(anon, monkeypatch, google):
    def bad(_):
        raise ValueError("Token expired")
    monkeypatch.setattr(auth_router, "verify_google_token", bad)
    assert anon.post("/auth/google", json=TOKEN).status_code == 401


def test_production_refuses_unsafe_defaults(monkeypatch):
    s = config.Settings()
    monkeypatch.setattr(s, "ENV", "production")
    monkeypatch.setattr(s, "SECRET_KEY", "change-this-to-a-long-random-string")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.check()
    monkeypatch.setattr(s, "SECRET_KEY", "k" * 48)
    monkeypatch.setattr(s, "SEED_PASSWORD", "a-long-unguessable-pass")
    monkeypatch.setattr(s, "SESSION_SECURE", True)
    s.check()  # all good: no error
