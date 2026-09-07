"""waiting list + client names

Revision ID: 004
Revises: 003
Create Date: 2026-09-07

- queue_items.status: agrega valor WAITING (solo MySQL necesita ALTER del ENUM;
  en SQLite el Enum es VARCHAR y no requiere cambios).
- venues.require_approval: toggle del admin (True = todo a espera).
- venue_clients: nombres únicos por local.

Defensiva (inspector checks): si una base de desarrollo ya tiene parte de los
cambios, los pasos existentes se omiten en vez de fallar.
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

_QUEUE_STATUS_VALUES = ('PENDING', 'PLAYING', 'PLAYED', 'SKIPPED', 'REMOVED', 'WAITING')


def _mysql_enum_values(bind, table: str, column: str) -> tuple | None:
    """Lee los valores actuales de una columna ENUM en MySQL."""
    row = bind.execute(
        sa.text(
            "SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    ).fetchone()
    if not row:
        return None
    coltype = row[0]
    if not coltype.upper().startswith("ENUM"):
        return None
    import re
    return tuple(re.findall(r"'([^']*)'", coltype))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. ENUM status: agregar WAITING (solo MySQL lo necesita)
    if bind.dialect.name == "mysql":
        current = _mysql_enum_values(bind, "queue_items", "status")
        if current is not None and "WAITING" not in current:
            values = [v for v in current if v in _QUEUE_STATUS_VALUES] + ["WAITING"]
            quoted = ",".join(f"'{v}'" for v in values)
            op.execute(f"ALTER TABLE queue_items MODIFY status ENUM({quoted}) NOT NULL")

    # 2. venues.require_approval (default True = todo a espera)
    venue_cols = {c["name"] for c in inspector.get_columns("venues")}
    if "require_approval" not in venue_cols:
        op.add_column(
            'venues',
            sa.Column('require_approval', sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # 3. venue_clients (el index de `id` lo crea el propio CREATE TABLE por index=True)
    if "venue_clients" not in inspector.get_table_names():
        op.create_table(
            'venue_clients',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('venue_id', sa.Integer(), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('display_name', sa.String(30), nullable=False),
            sa.Column('device_fingerprint', sa.String(128), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('venue_id', 'display_name', name='uq_venue_client_name'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "venue_clients" in inspector.get_table_names():
        op.drop_table('venue_clients')

    venue_cols = {c["name"] for c in inspector.get_columns("venues")}
    if "require_approval" in venue_cols:
        op.drop_column('venues', 'require_approval')

    if bind.dialect.name == "mysql":
        current = _mysql_enum_values(bind, "queue_items", "status")
        if current is not None and "WAITING" in current:
            values = [v for v in current if v != "WAITING"]
            quoted = ",".join(f"'{v}'" for v in values)
            op.execute(f"ALTER TABLE queue_items MODIFY status ENUM({quoted}) NOT NULL")
