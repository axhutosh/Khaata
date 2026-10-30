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

    # Open sign-up: anyone can create an account (email + password) and gets their own,
    # separate Khaata. OPEN_SIGNUP=false makes new accounts invite-only (ALLOWED_EMAILS).
    OPEN_SIGNUP: bool = _bool("OPEN_SIGNUP", True)
    ALLOWED_EMAILS: set[str] = {e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}

    def may_sign_up(self, email: str) -> bool:
        return self.OPEN_SIGNUP or email in self.ALLOWED_EMAILS

    # Encrypts stored bank narrations (app/crypto.py). Required. Comma-separate to rotate.
    DATA_KEY: str = os.getenv("DATA_KEY", "").strip()

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
        if not self.DATA_KEY:  # without it nothing can be stored or read: refuse in every mode
            raise RuntimeError("DATA_KEY is not set. Generate one and add it to backend/.env: "
                               "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        if self.production and not self.SESSION_SECURE:
            problems.append("SESSION_SECURE must be on in production (cookies over HTTPS only)")
        if problems and self.production:
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
        for p in problems:
            log.warning("SECURITY: %s", p)


settings = Settings()
