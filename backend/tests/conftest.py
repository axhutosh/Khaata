import os
import pathlib
import tempfile

import pytest

# point the app at a throwaway DB before it is imported
_db = pathlib.Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_EMAIL"] = "me@khaata.in"
os.environ["ALLOWED_EMAILS"] = "me@khaata.in"
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
from cryptography.fernet import Fernet  # noqa: E402
TEST_DATA_KEY = Fernet.generate_key().decode()
os.environ["DATA_KEY"] = TEST_DATA_KEY

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"
LOCKED = SAMPLES / "SBI_sample_locked.pdf"
UNLOCKED = SAMPLES / "SBI_sample.pdf"
PASSWORD = "ASHUT1947"


def google_token(email="me@khaata.in", sub="google-123", verified=True) -> str:
    """A stand-in for Google's ID token; the fake verifier below reads these fields back."""
    return f"test-google-id-token|{email}|{sub}|{int(verified)}"


def _fake_verify(credential: str) -> dict:
    try:
        _, email, sub, verified = credential.split("|")
    except ValueError:
        raise ValueError("Wrong number of segments in token")
    return {"email": email, "sub": sub, "email_verified": verified == "1"}


@pytest.fixture(autouse=True)
def fake_google(monkeypatch):
    """Tests never call Google: ID-token verification is replaced by _fake_verify."""
    monkeypatch.setattr(auth_router, "verify_google_token", _fake_verify)


@pytest.fixture
def anon():
    """A client with a fresh database and no session."""
    from app.security import login_throttle
    login_throttle.reset()
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    from app.security import login_throttle
    login_throttle.reset()
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan recreates tables and seeds the user
        assert c.post("/auth/google", json={"credential": google_token()}).status_code == 200
        yield c


def preview(client, path=LOCKED, password=PASSWORD):
    data = {"password": password} if password else {}
    return client.post("/upload/preview", data=data,
                       files={"file": (path.name, path.read_bytes(), "application/pdf")})
