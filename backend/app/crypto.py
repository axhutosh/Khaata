"""Encryption at rest for bank narrations (PRD §7).

`raw_narration` holds UPI IDs, account fragments, reference numbers and people's names, so
it's stored as a Fernet token (AES-128-CBC + HMAC-SHA256, random IV). Amounts, dates,
merchants and categories stay plaintext so SQL can still group and sum them.

The key lives in DATA_KEY (backend/.env), never in the database. DATA_KEY may list several
comma-separated keys: the first encrypts, all of them decrypt. To rotate, put a new key in
front and restart; startup re-encrypts every row under it, then the old key can go.

Lose every key and the narrations are gone for good. Back DATA_KEY up.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import shutil
import time
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text, text
from sqlalchemy.types import TypeDecorator

from .config import settings

log = logging.getLogger("khaata")
TOKEN_PREFIX = "gAAAAA"  # every Fernet token starts like this (version byte + timestamp)


class DataKeyError(RuntimeError):
    """DATA_KEY is missing, malformed, or doesn't match the stored data."""


_cache: tuple[str, MultiFernet, Fernet] | None = None


def _ciphers() -> tuple[MultiFernet, Fernet]:
    global _cache
    raw = settings.DATA_KEY
    if _cache and _cache[0] == raw:
        return _cache[1], _cache[2]
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise DataKeyError("DATA_KEY is not set (see backend/.env.example)")
    try:
        fernets = [Fernet(k) for k in keys]
    except (ValueError, TypeError):
        raise DataKeyError("DATA_KEY isn't a valid key: each one must be 44 characters of url-safe base64 "
                           "(generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")")
    _cache = (raw, MultiFernet(fernets), fernets[0])
    return _cache[1], _cache[2]


def reset() -> None:
    """Forget the cached cipher (tests change DATA_KEY)."""
    global _cache
    _cache = None


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(TOKEN_PREFIX)


def encrypt(plain: str) -> str:
    return _ciphers()[1].encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(value: str) -> str:
    if not is_encrypted(value):  # not yet migrated; startup encrypts these
        return value
    try:
        return _ciphers()[0].decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise DataKeyError("Can't decrypt stored narrations: DATA_KEY doesn't match the key they were "
                           "encrypted with. Restore the right key in backend/.env.")


def keyed_hash(message: str) -> str:
    """Duplicate-detection key. A plain SHA-256 of a narration could be brute-forced back to
    it; an HMAC needs the secret too. Keyed off the primary DATA_KEY (separated by a label,
    so the hash key is never the encryption key itself)."""
    _ciphers()  # validates DATA_KEY
    primary = base64.urlsafe_b64decode(settings.DATA_KEY.split(",")[0].strip())
    secret = hmac.new(primary, b"khaata-dedupe-v1", hashlib.sha256).digest()
    return hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


class EncryptedText(TypeDecorator):
    """A text column stored encrypted; reads and writes plaintext in Python."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)


def dedupe_message(user_id: str, txn_date, amount, txn_type: str, narration: str) -> str:
    """The same string for a parsed row and a stored one: ISO date, amount to 2 places."""
    return f"{user_id}|{str(txn_date)[:10]}|{Decimal(str(amount)):.2f}|{txn_type}|{narration}"


def migrate(conn, database_url: str) -> int:
    """Bring every transaction row up to date: encrypt plaintext narrations (legacy rows),
    re-encrypt rows under a rotated-out key, and recompute their keyed dedupe hash.
    Backs the SQLite file up first if anything needs changing. Returns rows changed."""
    multi, primary = _ciphers()
    rows = conn.execute(text("SELECT id, user_id, txn_date, amount, txn_type, raw_narration FROM transactions")).all()
    todo = []
    for r in rows:
        value = r.raw_narration or ""
        if not is_encrypted(value):
            todo.append((r, value))
            continue
        try:
            primary.decrypt(value.encode("ascii"))
        except InvalidToken:  # encrypted, but not with the current primary key
            todo.append((r, decrypt(value)))
    if not todo:
        return 0

    if database_url.startswith("sqlite:///"):
        db_file = Path(database_url.removeprefix("sqlite:///"))
        if db_file.exists():
            backup = db_file.with_name(f"{db_file.stem}-backup-before-encryption-{time.strftime('%Y%m%d-%H%M%S')}.db")
            shutil.copy2(db_file, backup)
            log.warning("Encrypting %d stored narrations; backup of the database saved as %s", len(todo), backup.name)

    for r, plain in todo:
        conn.execute(text("UPDATE transactions SET raw_narration = :n, txn_hash = :h WHERE id = :id"),
                     {"n": encrypt(plain), "id": r.id,
                      "h": keyed_hash(dedupe_message(r.user_id, r.txn_date, r.amount, r.txn_type, plain))})
    return len(todo)
