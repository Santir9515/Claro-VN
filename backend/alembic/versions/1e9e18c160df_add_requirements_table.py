"""add requirements table

Revision ID: 1e9e18c160df
Revises: 6511f37c20ab
Create Date: 2026-02-27 00:21:19.846861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e9e18c160df'
down_revision: Union[str, None] = '6511f37c20ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("minute", sa.SmallInteger(), nullable=False),
        sa.Column("required", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("campaign_id", "period", "weekday", "minute", name="uq_requirements"),
    )


def downgrade() -> None:
    op.drop_table("requirements")

    
