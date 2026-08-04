import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, func, Numeric, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    parent_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    icon: Mapped[str] = mapped_column(String(50), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    children: Mapped[list["Category"]] = relationship("Category", backref="parent", remote_side="Category.id")


class TransactionCategory(Base):
    __tablename__ = "transaction_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    assigned_by: Mapped[str] = mapped_column(String(50), default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="categories")
    category: Mapped["Category"] = relationship("Category")
