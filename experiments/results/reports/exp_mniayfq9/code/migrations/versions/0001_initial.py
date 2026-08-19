"""Initial user, category, and task tables."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),
    )
    op.create_index("ix_categories_owner_id", "categories", ["owner_id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("status", "priority", "due_date", "creator_id", "assignee_id", "category_id"):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])


def downgrade():
    op.drop_table("tasks")
    op.drop_table("categories")
    op.drop_table("users")
