"""create comments table

Revision ID: 0002_create_comments
Revises: 0001_create_tickets
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_create_comments"
down_revision = "0001_create_tickets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_comments_ticket_id", "comments", ["ticket_id"])


def downgrade():
    op.drop_index("ix_comments_ticket_id", table_name="comments")
    op.drop_table("comments")
