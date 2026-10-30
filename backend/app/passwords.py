"""Password hashing (scrypt, from the standard library) and the rules for NEW passwords.

The rules apply when a password is chosen (sign-up, tools/set_password.py) — never at
sign-in. frontend/src/passwordRules.js mirrors them so people see problems while typing.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

# scrypt cost: ~16 MB and tens of milliseconds per check — cheap for a sign-in, costly for a guesser
N, R, P = 2 ** 14, 8, 1
MIN_LENGTH, PASSPHRASE_LENGTH, MAX_LENGTH = 12, 16, 128

# Words guessers try first. Checked after lower-casing, undoing l33t-speak and dropping
# digits/symbols, so "P@ssw0rd2024!" still counts as "password".
COMMON = set("""
password passwd pass qwerty qwertyuiop asdf asdfgh asdfghjkl zxcvbnm iloveyou love lover welcome admin
administrator letmein login monkey dragon sunshine princess football cricket baseball soccer hockey
superman batman spiderman shadow master secret hello freedom whatever trustno trustme abc abcd abcdef
abcdefg abcdefgh test tester testing guest user default changeme money india bharat hindustan khaata
ganesh krishna shiva sairam jaishriram mumbai delhi bangalore chennai kolkata hyderabad pune iloveindia
mother father family friends forever beautiful angel samsung iphone apple google facebook instagram
whatsapp computer internet starwars pokemon naruto michael jordan charlie thomas daniel
""".split())

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s",
                       "!": "i", "|": "i", "+": "t"})
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")


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


def _classes(pw: str) -> int:
    return sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))


def _has_run(pw: str, length: int = 4) -> bool:
    """aaaa, abcd / dcba, 1234 / 4321, or 4 keys in a row on the keyboard (qwer, asdf)."""
    s = pw.lower()
    for i in range(len(s) - length + 1):
        chunk = s[i:i + length]
        if len(set(chunk)) == 1:
            return True
        steps = {ord(b) - ord(a) for a, b in zip(chunk, chunk[1:])}
        if steps in ({1}, {-1}) and chunk.isalnum():
            return True
        if any(chunk in row or chunk in row[::-1] for row in _ROWS):
            return True
    return False


def _is_common(pw: str) -> bool:
    # "P@ssw0rd2024!" -> drop the digits/symbols tacked on the ends -> undo l33t -> "password"
    trimmed = re.sub(r"^[\W\d_]+|[\W\d_]+$", "", pw.lower())
    core = re.sub(r"[^a-z]", "", trimmed.translate(_LEET))
    if len(core) < 4 or core in COMMON or any(core == w * 2 for w in COMMON):
        return True
    # a common word of 5+ letters anywhere ("MyPassword!9") is still the first thing guessed
    whole = re.sub(r"[^a-z]", "", pw.lower().translate(_LEET))
    return any(len(w) >= 5 and w in whole for w in COMMON)


def checks(password: str, email: str) -> list[tuple[str, bool]]:
    """Every rule with whether it passes — the same list the sign-up form shows."""
    local = email.split("@")[0].lower()
    long_phrase = len(password) >= PASSPHRASE_LENGTH
    return [
        (f"At least {MIN_LENGTH} characters", MIN_LENGTH <= len(password) <= MAX_LENGTH),
        ("Mix of upper and lower case, numbers or symbols — or 16+ characters",
         _classes(password) >= (2 if long_phrase else 3)),
        ("Not a common or easily guessed password", not _is_common(password)),
        ("No runs like 1234, abcd, qwer or aaaa", not _has_run(password)),
        ("Doesn't contain your email name", not (len(local) >= 4 and local in password.lower())),
    ]


def strength(password: str, email: str) -> int:
    """0-4 for the meter: 0 until every rule passes, then length and variety add up."""
    if not all(ok for _, ok in checks(password, email)):
        return 1 if len(password) >= 8 else 0
    return min(4, 2 + (len(password) >= 16) + (_classes(password) == 4))


def password_problem(password: str, email: str) -> str | None:
    """Why this new password isn't acceptable, or None if it is."""
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    for rule, ok in checks(password, email):
        if not ok:
            return f"Password needs: {rule[0].lower()}{rule[1:]}."
    return None
