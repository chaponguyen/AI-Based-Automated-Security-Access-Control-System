"""Tao 3 bang staff_accounts, staff_sessions, audit_logs cho B15

Revision ID: 7e3d1a8c9012
Revises: 01f66c7fc85b
Create Date: 2026-10-26 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e3d1a8c9012'
down_revision: Union[str, None] = '01f66c7fc85b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. staff_accounts
    op.create_table(
        'staff_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("role in ('security','manager')", name='ck_staff_accounts_role'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username', name='uq_staff_accounts_username'),
    )
    op.create_index(op.f('ix_staff_accounts_username'), 'staff_accounts', ['username'], unique=True)

    # 2. staff_sessions
    op.create_table(
        'staff_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_staff_sessions_token_hash'),
    )
    op.create_index(op.f('ix_staff_sessions_token_hash'), 'staff_sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_staff_sessions_staff_id'), 'staff_sessions', ['staff_id'], unique=False)

    # 3. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=True),
        sa.Column('staff_username', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=30), nullable=True),
        sa.Column('target_id', sa.String(length=50), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_staff_id'), 'audit_logs', ['staff_id'], unique=False)


def downgrade() -> None:
    # Xoa nguoc thu tu de thoa man rang buoc khoa ngoai
    # 1. audit_logs
    op.drop_index(op.f('ix_audit_logs_staff_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_table('audit_logs')

    # 2. staff_sessions
    op.drop_index(op.f('ix_staff_sessions_staff_id'), table_name='staff_sessions')
    op.drop_index(op.f('ix_staff_sessions_token_hash'), table_name='staff_sessions')
    op.drop_table('staff_sessions')

    # 3. staff_accounts
    op.drop_index(op.f('ix_staff_accounts_username'), table_name='staff_accounts')
    op.drop_table('staff_accounts')
