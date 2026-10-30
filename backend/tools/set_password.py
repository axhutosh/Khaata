"""Set (or reset) an account's password. Run from backend/:

    .venv/Scripts/python tools/set_password.py you@example.com

Prompts twice (input hidden) and applies the same rules as sign-up. Existing sign-ins stay
valid; to sign every device out, change SECRET_KEY in .env and restart the backend.
"""
import getpass
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.passwords import hash_password, password_problem  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1].strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"No account with email {email}.", file=sys.stderr)
            return 1
        pw = getpass.getpass("New password: ")
        problem = password_problem(pw, email)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        if getpass.getpass("Again: ") != pw:
            print("Passwords didn't match.", file=sys.stderr)
            return 1
        user.password_hash = hash_password(pw)
        db.commit()
        print(f"Password set for {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
