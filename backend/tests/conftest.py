import os
import pathlib
import tempfile

import pytest

# point the app at a throwaway DB before it is imported
_db = pathlib.Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
from cryptography.fernet import Fernet  # noqa: E402
TEST_DATA_KEY = Fernet.generate_key().decode()
os.environ["DATA_KEY"] = TEST_DATA_KEY

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"
LOCKED = SAMPLES / "SBI_sample_locked.pdf"
UNLOCKED = SAMPLES / "SBI_sample.pdf"
PASSWORD = "ASHUT1947"


EMAIL, ACCOUNT_PASSWORD = "me@khaata.in", "correct horse battery"


def creds(email=EMAIL, password=ACCOUNT_PASSWORD) -> dict:
    return {"email": email, "password": password}


def _reset():
    from app.security import login_throttle, signup_throttle
    login_throttle.reset()
    signup_throttle.reset()
    Base.metadata.drop_all(engine)


@pytest.fixture
def anon():
    """A client with a fresh database and no session."""
    _reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    """Signed up and signed in as EMAIL, on a fresh database."""
    _reset()
    with TestClient(app) as c:  # lifespan recreates the tables
        assert c.post("/auth/signup", json=creds()).status_code == 200
        yield c


def preview(client, path=LOCKED, password=PASSWORD):
    data = {"password": password} if password else {}
    return client.post("/upload/preview", data=data,
                       files={"file": (path.name, path.read_bytes(), "application/pdf")})
