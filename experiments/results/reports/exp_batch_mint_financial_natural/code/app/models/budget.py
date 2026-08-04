import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="budgets")
    items: Mapped[list["BudgetItem"]] = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    budget_id: Mapped[str] = mapped_column(String(36), ForeignKey("budgets.id"), nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    alert_threshold_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=80.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    budget: Mapped["Budget"] = relationship("Budget", back_populates="items")
    category: Mapped["Category"] = relationship("Category")
