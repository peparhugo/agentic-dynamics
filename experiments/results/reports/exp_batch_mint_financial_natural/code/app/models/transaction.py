import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    post_date: Mapped[date] = mapped_column(Date, nullable=True)
    is_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[str] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["FinancialAccount"] = relationship("FinancialAccount", back_populates="transactions")
    categories: Mapped[list["TransactionCategory"]] = relationship(
        "TransactionCategory", back_populates="transaction", cascade="all, delete-orphan"
    )
