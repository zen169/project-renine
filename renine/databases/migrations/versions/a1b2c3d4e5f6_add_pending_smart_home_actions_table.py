"""add_pending_smart_home_actions_table

Revision ID: a1b2c3d4e5f6
Revises: 8fbc76e8a4d2
Create Date: 2026-06-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8fbc76e8a4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade(engine_name: str) -> None:
    """Upgrade schema."""
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name: str) -> None:
    """Downgrade schema."""
    globals()["downgrade_%s" % engine_name]()


def upgrade_history() -> None:
    """Upgrade history schema (no-op for this migration)."""
    pass


def downgrade_history() -> None:
    """Downgrade history schema (no-op for this migration)."""
    pass


def upgrade_mind() -> None:
    """Upgrade mind schema — add pending_smart_home_actions table."""
    op.create_table(
        'pending_smart_home_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.String(length=256), nullable=False),
        sa.Column('domain', sa.String(length=64), nullable=False),
        sa.Column('service', sa.String(length=64), nullable=False),
        sa.Column('service_data', sa.JSON(), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_pending_smart_home_actions_entity_id',
        'pending_smart_home_actions',
        ['entity_id'],
        unique=False,
    )
    op.create_index(
        'ix_pending_smart_home_actions_status',
        'pending_smart_home_actions',
        ['status'],
        unique=False,
    )


def downgrade_mind() -> None:
    """Downgrade mind schema — drop pending_smart_home_actions table."""
    op.drop_index(
        'ix_pending_smart_home_actions_status',
        table_name='pending_smart_home_actions',
    )
    op.drop_index(
        'ix_pending_smart_home_actions_entity_id',
        table_name='pending_smart_home_actions',
    )
    op.drop_table('pending_smart_home_actions')


def upgrade_personality() -> None:
    """Upgrade personality schema (no-op for this migration)."""
    pass


def downgrade_personality() -> None:
    """Downgrade personality schema (no-op for this migration)."""
    pass
