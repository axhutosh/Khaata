from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy import inspect, text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from .models import User
from .auth import current_user, hash_password, verify_password
from .security import OriginCheck, SecurityHeaders
from .routers import auth, upload, uploads, transactions, insights, budgets


def seed_user():
    db = SessionLocal()
    try:
        email = settings.SEED_EMAIL.lower()
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, password_hash=hash_password(settings.SEED_PASSWORD)))
            db.commit()
    finally:
        db.close()


def migrate_data():
    """Small in-place schema/data fixes until Alembic arrives."""
    with engine.begin() as conn:
        for table in ("transactions", "merchant_rules", "budgets"):  # category renamed
            conn.execute(text(f"UPDATE {table} SET category = 'P2P Transfer' "
                              "WHERE category = 'Transfer · Person'"))
        if "google_sub" not in {c["name"] for c in inspect(conn).get_columns("users")}:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"))


def weak_password_users() -> list[str]:
    """Accounts whose real (stored) password is a default or too short to be safe.
    SEED_PASSWORD only matters when the account is first created, so check the database."""
    weak = [settings.SEED_PASSWORD] if len(settings.SEED_PASSWORD) < 10 else []
    db = SessionLocal()
    try:
        return [u.email for u in db.query(User).all()
                if any(verify_password(pw, u.password_hash) for pw in ("password", *weak))]
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_data()
    seed_user()
    settings.check(weak_password_users())
    yield


# interactive API docs only in development
docs = {} if not settings.production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Khaata API", lifespan=lifespan, **docs)

# outermost first: headers on every response, then CSRF check, then CORS, then the session
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="khaata_session",
                   max_age=settings.SESSION_MAX_AGE, same_site="lax", https_only=settings.SESSION_SECURE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(OriginCheck, allowed=settings.CORS_ORIGINS)
app.add_middleware(SecurityHeaders)

# public: sign-in only. Everything else needs a session, enforced on the whole router so a
# new endpoint can't ship unauthenticated by forgetting the dependency.
app.include_router(auth.router)
for r in (upload, uploads, transactions, insights, budgets):
    app.include_router(r.router, dependencies=[Depends(current_user)])


@app.get("/health")
def health():
    return {"ok": True}
