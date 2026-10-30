from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy import inspect, text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from .models import User
from .auth import current_user
from .security import OriginCheck, SecurityHeaders
from .routers import auth, upload, uploads, transactions, insights, budgets
from .routers.auth import NO_PASSWORD


def seed_user():
    if not settings.SEED_EMAIL:
        return
    db = SessionLocal()
    try:
        email = settings.SEED_EMAIL.lower()
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, password_hash=NO_PASSWORD))
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
        # sign-in is Google only: drop any stored password hash so no password route exists
        conn.execute(text("UPDATE users SET password_hash = :p WHERE password_hash != :p"), {"p": NO_PASSWORD})


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_data()
    seed_user()
    settings.check()
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
