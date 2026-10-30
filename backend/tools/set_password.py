"""Set (or reset) a user's password. Run from backend/:

    python tools/set_password.py you@email.com

Prompts twice (input hidden). Existing sign-ins stay valid; to sign out every device,
change SECRET_KEY in .env and restart the backend.
"""
import getpass
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1].strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"No user with email {email}.", file=sys.stderr)
            return 1
        pw = getpass.getpass("New password (10+ characters): ")
        if len(pw) < 10:
            print("Too short — use at least 10 characters.", file=sys.stderr)
            return 1
        if getpass.getpass("Again: ") != pw:
            print("Passwords didn't match.", file=sys.stderr)
            return 1
        user.password_hash = hash_password(pw)
        db.commit()
        print(f"Password updated for {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
