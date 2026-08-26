"""add genre to songs

Revision ID: 002
Revises: 001_initial_schema
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('songs', sa.Column('genre', sa.String(100), nullable=True))
    op.create_index(op.f('ix_songs_genre'), 'songs', ['genre'])


def downgrade() -> None:
    op.drop_index(op.f('ix_songs_genre'), table_name='songs')
    op.drop_column('songs', 'genre')
