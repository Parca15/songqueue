"""create users table (super admin)

Revision ID: 005
Revises: 004
Create Date: 2026-09-08

Tabla de usuarios globales del sistema (rol superadmin).
El registro inicial se crea en el arranque desde variables de entorno.
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('username', sa.String(100), nullable=False, index=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('role', sa.String(20), nullable=False, server_default='superadmin'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('username', name='uq_users_username'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" in inspector.get_table_names():
        op.drop_table('users')
