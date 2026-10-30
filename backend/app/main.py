from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from .models import User
from .auth import hash_password
from .routers import auth, upload, uploads, transactions, insights, budgets


def seed_user():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.SEED_EMAIL).first():
            db.add(User(email=settings.SEED_EMAIL,
                        password_hash=hash_password(settings.SEED_PASSWORD)))
            db.commit()
    finally:
        db.close()


def migrate_data():
    """Small in-place data fixes until Alembic arrives."""
    with engine.begin() as conn:
        for table in ("transactions", "merchant_rules", "budgets"):  # category renamed
            conn.execute(text(f"UPDATE {table} SET category = 'P2P Transfer' "
                              "WHERE category = 'Transfer · Person'"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_data()
    seed_user()
    yield


app = FastAPI(title="Khaata API", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, same_site="lax")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, upload, uploads, transactions, insights, budgets):
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"ok": True}
