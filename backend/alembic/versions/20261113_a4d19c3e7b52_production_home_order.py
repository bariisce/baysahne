"""production home_order: editor-curated order of the home screen's repertoire strip

Revision ID: a4d19c3e7b52
Revises: cf720eba73c5
Create Date: 2026-11-13 16:40:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a4d19c3e7b52'
down_revision: str | None = 'cf720eba73c5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('productions', sa.Column('home_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('productions', 'home_order')
