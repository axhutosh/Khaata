import os
import pathlib
import tempfile

import pytest

# point the app at a throwaway DB before it is imported
_db = pathlib.Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_EMAIL"] = "me@khaata.in"
os.environ["SEED_PASSWORD"] = "pw"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"
LOCKED = SAMPLES / "SBI_sample_locked.pdf"
UNLOCKED = SAMPLES / "SBI_sample.pdf"
PASSWORD = "ASHUT1947"


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan recreates tables and seeds the user
        assert c.post("/auth/login", json={"email": "me@khaata.in", "password": "pw"}).status_code == 200
        yield c


def preview(client, path=LOCKED, password=PASSWORD):
    data = {"password": password} if password else {}
    return client.post("/upload/preview", data=data,
                       files={"file": (path.name, path.read_bytes(), "application/pdf")})
