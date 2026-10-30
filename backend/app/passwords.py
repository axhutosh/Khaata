"""Password hashing (scrypt, from the standard library) and the password rules."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# scrypt cost: ~16 MB and tens of milliseconds per check — cheap for a sign-in, costly for a guesser
N, R, P = 2 ** 14, 8, 1
MIN_LENGTH, MAX_LENGTH = 10, 128

# the handful of passwords guessers try first; anything here is refused outright
COMMON = {
    "password", "password1", "password12", "password123", "1234567890", "12345678910", "qwertyuiop",
    "qwerty1234", "qwerty12345", "iloveyou12", "letmein123", "welcome123", "admin12345", "abcdefghij",
    "1111111111", "0000000000", "1234512345", "asdfghjkl1", "india12345", "khaata1234", "changeme12",
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return f"scrypt${N}${R}${P}${b64(salt)}${b64(digest)}"


# compared against when the email doesn't exist, so a wrong email costs the same time
# as a wrong password and response timing doesn't reveal which accounts exist
_DUMMY = hash_password("not-a-real-password-just-for-timing")


def verify_password(password: str, stored: str | None) -> bool:
    try:
        scheme, n, r, p, salt, digest = (stored or _DUMMY).split("$")
        if scheme != "scrypt":
            raise ValueError
        got = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt),
                             n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(digest)) and stored is not None
    except (ValueError, TypeError):  # unusable or legacy hash: never matches
        hashlib.scrypt(b"x", salt=b"0" * 16, n=N, r=R, p=P, dklen=32)  # keep timing even
        return False


def password_problem(password: str, email: str) -> str | None:
    """Why this password isn't acceptable, or None if it is."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    lowered = password.lower()
    if lowered in COMMON or len(set(password)) < 4:
        return "That password is too easy to guess. Try a short phrase of a few words."
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in lowered:
        return "Don't use your email address in your password."
    return None
