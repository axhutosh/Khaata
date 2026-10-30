import sqlite3

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from app import config, crypto
from app.database import engine
from conftest import TEST_DATA_KEY, preview


@pytest.fixture(autouse=True)
def fresh_cipher():
    crypto.reset()
    yield
    crypto.reset()


def _raw_rows():
    with engine.connect() as c:
        return c.execute(text("SELECT raw_narration, txn_hash FROM transactions")).all()


def _commit(client):
    return client.post("/upload/commit", json={"token": preview(client).json()["token"]}).json()


def test_round_trip_and_random_iv():
    a, b = crypto.encrypt("UPI/DR/1/RAMESH"), crypto.encrypt("UPI/DR/1/RAMESH")
    assert a != b and crypto.is_encrypted(a)
    assert crypto.decrypt(a) == crypto.decrypt(b) == "UPI/DR/1/RAMESH"


def test_narrations_are_ciphertext_in_the_database_but_plain_through_the_api(client):
    _commit(client)
    stored = _raw_rows()
    assert stored and all(crypto.is_encrypted(n) for n, _ in stored)
    assert not any("UPI" in n or "TRANSFER" in n for n, _ in stored)
    api = client.get("/transactions?limit=1000").json()
    assert any("UPI" in t["raw"] for t in api)


def test_dedupe_hash_is_keyed(client):
    _commit(client)
    hashes = {h for _, h in _raw_rows()}
    assert all(len(h) == 32 for h in hashes)
    assert _commit(client)["saved"] == 0  # re-upload: all duplicates, so keyed hashes are stable


def test_search_still_finds_text_inside_the_narration(client):
    _commit(client)
    every = client.get("/transactions?limit=1000").json()
    word = "TRANSFER"
    expected = [t for t in every if word.lower() in t["raw"].lower() or word.lower() in t["merchant"].lower()]
    assert expected
    found = client.get(f"/transactions?q={word.lower()}&limit=1000").json()
    assert len(found) == len(expected)


def test_legacy_plaintext_rows_are_encrypted_on_startup(client):
    _commit(client)
    with engine.begin() as c:  # pretend these rows predate encryption
        c.execute(text("UPDATE transactions SET raw_narration = 'LEGACY-' || id, txn_hash = 'old-' || id"))
    with engine.begin() as c:
        changed = crypto.migrate(c, "sqlite:///not-a-real-file.db")
    assert changed == len(_raw_rows())
    assert all(crypto.is_encrypted(n) and not h.startswith("old-") for n, h in _raw_rows())
    api = client.get("/transactions?limit=1000").json()
    assert all(t["raw"] == f"LEGACY-{t['id']}" for t in api)


def test_key_rotation_re_encrypts_under_the_new_key(client, monkeypatch):
    _commit(client)
    before = client.get("/transactions?limit=1000").json()
    new = Fernet.generate_key().decode()
    monkeypatch.setattr(config.settings, "DATA_KEY", f"{new},{TEST_DATA_KEY}")  # new key first, old kept
    crypto.reset()
    with engine.begin() as c:
        assert crypto.migrate(c, "sqlite:///not-a-real-file.db") == len(before)
        assert crypto.migrate(c, "sqlite:///not-a-real-file.db") == 0  # nothing left to do
    monkeypatch.setattr(config.settings, "DATA_KEY", new)  # old key dropped entirely
    crypto.reset()
    assert [t["raw"] for t in client.get("/transactions?limit=1000").json()] == [t["raw"] for t in before]
    assert _commit(client)["saved"] == 0  # hashes were recomputed under the new key


def test_wrong_key_fails_loudly(client, monkeypatch):
    _commit(client)
    monkeypatch.setattr(config.settings, "DATA_KEY", Fernet.generate_key().decode())
    crypto.reset()
    with pytest.raises(crypto.DataKeyError, match="doesn't match"):
        crypto.decrypt(_raw_rows()[0][0])


def test_missing_or_malformed_key_is_refused(monkeypatch):
    s = config.Settings()
    monkeypatch.setattr(s, "DATA_KEY", "")
    with pytest.raises(RuntimeError, match="DATA_KEY"):
        s.check()
    monkeypatch.setattr(config.settings, "DATA_KEY", "not-a-key")
    crypto.reset()
    with pytest.raises(crypto.DataKeyError, match="valid key"):
        crypto.encrypt("x")


def test_sqlite_backup_is_made_before_encrypting(tmp_path, monkeypatch):
    db = tmp_path / "k.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE transactions (id TEXT, user_id TEXT, txn_date TEXT, amount REAL, txn_type TEXT, "
                "raw_narration TEXT, txn_hash TEXT)")
    con.execute("INSERT INTO transactions VALUES ('1','u','2026-01-01',20.0,'debit','UPI/DR/1/A/B/c/UPI','old')")
    con.commit(); con.close()
    from sqlalchemy import create_engine
    eng = create_engine(f"sqlite:///{db.as_posix()}")
    with eng.begin() as c:
        assert crypto.migrate(c, f"sqlite:///{db.as_posix()}") == 1
    eng.dispose()
    backups = list(tmp_path.glob("k-backup-before-encryption-*.db"))
    assert len(backups) == 1
    assert sqlite3.connect(backups[0]).execute("SELECT raw_narration FROM transactions").fetchone()[0] == "UPI/DR/1/A/B/c/UPI"
