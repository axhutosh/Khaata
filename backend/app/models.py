import uuid, datetime as dt
from sqlalchemy import String, Numeric, Date, DateTime, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
from .crypto import EncryptedText


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "txn_hash", name="uq_user_txn"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    txn_date: Mapped[dt.date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))      # positive magnitude
    txn_type: Mapped[str] = mapped_column(String(6))           # debit / credit
    balance: Mapped[float] = mapped_column(Numeric(14, 2))
    raw_narration: Mapped[str] = mapped_column(EncryptedText)  # encrypted at rest (app/crypto.py)
    merchant: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, index=True)
    method: Mapped[str] = mapped_column(String(8))             # UPI / NEFT / ATM ...
    counterparty_kind: Mapped[str] = mapped_column(String(10)) # merchant / person / self / bank
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    upload_id: Mapped[str | None] = mapped_column(ForeignKey("uploads.id"), index=True, nullable=True)
    source_file: Mapped[str] = mapped_column(String)
    txn_hash: Mapped[str] = mapped_column(String, index=True)  # dedupe key


class Upload(Base):
    """One committed statement. Deleting it removes the rows it saved."""
    __tablename__ = "uploads"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    period_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    reconciles: Mapped[bool] = mapped_column(Boolean, default=False)


class MerchantRule(Base):
    """Learned mapping from a cleaned narration token to merchant + category.
    A correction on the Review screen writes a row here."""
    __tablename__ = "merchant_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String, index=True)
    merchant: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String)
    monthly_limit: Mapped[float] = mapped_column(Numeric(14, 2))
