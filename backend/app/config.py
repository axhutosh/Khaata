import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env; real environment variables win over it
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger("khaata")

PLACEHOLDER_SECRETS = {"", "dev-secret-change-me", "change-this-to-a-long-random-string"}


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    ENV: str = os.getenv("ENV", "development").lower()  # "production" turns on the strict checks
    # SQLite by default; set DATABASE_URL to a Postgres URL in production.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./khaata.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

    # The owner's account (solo v1): created at startup, signed in to with Google.
    SEED_EMAIL: str = os.getenv("SEED_EMAIL", "you@email.com")

    # Google sign-in (Google Identity Services) is the only way in. Required.
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    # Who may sign in. Solo v1: defaults to the seed email only.
    ALLOWED_EMAILS: set[str] = {e.strip().lower() for e in
                                os.getenv("ALLOWED_EMAILS", os.getenv("SEED_EMAIL", "you@email.com")).split(",")
                                if e.strip()}

    SESSION_MAX_AGE: int = int(os.getenv("SESSION_MAX_AGE", str(7 * 24 * 3600)))  # seconds
    SESSION_SECURE: bool = _bool("SESSION_SECURE", ENV == "production")  # cookie only over HTTPS
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "15"))

    @property
    def production(self) -> bool:
        return self.ENV == "production"

    def check(self) -> None:
        """Refuse unsafe defaults in production; warn about them in development."""
        problems = []
        if self.SECRET_KEY in PLACEHOLDER_SECRETS or len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY is a placeholder or shorter than 32 characters "
                            "(generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\")")
        if not self.GOOGLE_CLIENT_ID:
            problems.append("GOOGLE_CLIENT_ID is empty, so nobody can sign in (see README: Google sign-in)")
        if self.production and not self.SESSION_SECURE:
            problems.append("SESSION_SECURE must be on in production (cookies over HTTPS only)")
        if problems and self.production:
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
        for p in problems:
            log.warning("SECURITY: %s", p)


settings = Settings()
