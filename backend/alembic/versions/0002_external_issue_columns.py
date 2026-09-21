"""add severity, trigger_type, external_reporter to tasks (gRPC issue intake)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("severity", sa.String(10), nullable=True))
    op.add_column("tasks", sa.Column("trigger_type", sa.String(20), nullable=True))
    op.add_column("tasks", sa.Column("external_reporter", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "external_reporter")
    op.drop_column("tasks", "trigger_type")
    op.drop_column("tasks", "severity")
