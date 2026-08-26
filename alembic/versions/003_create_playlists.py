"""create playlists

Revision ID: 003
Revises: 002
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'playlists',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('venue_id', sa.Integer(), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'playlist_items',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('playlist_id', sa.Integer(), sa.ForeignKey('playlists.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('song_id', sa.Integer(), sa.ForeignKey('songs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('playlist_items')
    op.drop_table('playlists')
