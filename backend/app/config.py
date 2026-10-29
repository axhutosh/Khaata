import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env; real environment variables win over it
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    # SQLite by default; set DATABASE_URL to a Postgres URL in production.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./khaata.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Seed single user (solo v1). Change in .env.
    SEED_EMAIL: str = os.getenv("SEED_EMAIL", "you@email.com")
    SEED_PASSWORD: str = os.getenv("SEED_PASSWORD", "password")


settings = Settings()
