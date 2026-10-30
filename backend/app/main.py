from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine
from .auth import current_user
from . import crypto
from .security import OriginCheck, SecurityHeaders
from .routers import auth, upload, uploads, transactions, insights, budgets


def migrate_data():
    """Small in-place schema/data fixes until Alembic arrives."""
    with engine.begin() as conn:
        for table in ("transactions", "merchant_rules", "budgets"):  # category renamed
            conn.execute(text(f"UPDATE {table} SET category = 'P2P Transfer' "
                              "WHERE category = 'Transfer · Person'"))
        # narrations encrypted at rest; also re-encrypts after a key rotation
        crypto.migrate(conn, settings.DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.check()  # first: the migration below needs DATA_KEY
    Base.metadata.create_all(bind=engine)
    migrate_data()
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

# public: sign-up / sign-in only. Everything else needs a session, enforced on the whole router so a
# new endpoint can't ship unauthenticated by forgetting the dependency.
app.include_router(auth.router)
for r in (upload, uploads, transactions, insights, budgets):
    app.include_router(r.router, dependencies=[Depends(current_user)])


@app.get("/health")
def health():
    return {"ok": True}
