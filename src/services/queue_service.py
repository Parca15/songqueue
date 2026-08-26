"""
Servicio de gestión de colas.
Lógica de negocio para agregar, reordenar y eliminar canciones.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from src.models.queue_item import QueueItem, QueueStatus
from src.models.song import Song
from src.models.venue import Venue
from src.schemas.queue import QueueItemCreate, QueueReorder


async def get_queue_by_venue(db: AsyncSession, venue_id: int) -> list[QueueItem]:
    """Obtiene todos los items de la cola de un local ordenados por posición."""
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(
            QueueItem.venue_id == venue_id,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
        .order_by(QueueItem.position)
    )
    return result.scalars().all()


async def get_now_playing(db: AsyncSession, venue_id: int) -> QueueItem | None:
    """Obtiene la canción que está sonando actualmente."""
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.PLAYING,
        )
    )
    return result.scalar_one_or_none()


async def add_song_to_queue(
    db: AsyncSession,
    venue_id: int,
    song: Song,
    item_data: QueueItemCreate,
) -> QueueItem:
    """Agrega una canción al final de la cola."""
    # Obtener la última posición
    result = await db.execute(
        select(func.max(QueueItem.position)).where(
            QueueItem.venue_id == venue_id,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
    )
    last_position = result.scalar() or 0

    queue_item = QueueItem(
        venue_id=venue_id,
        song_id=song.id,
        device_fingerprint=item_data.device_fingerprint,
        position=last_position + 1,
        status=QueueStatus.PENDING,
        requested_by=item_data.requested_by,
    )
    db.add(queue_item)
    await db.commit()
    await db.refresh(queue_item)
    return queue_item


async def reorder_queue(db: AsyncSession, venue_id: int, reorder: QueueReorder) -> list[QueueItem]:
    """Reordena la cola según el orden de IDs proporcionado."""
    for idx, item_id in enumerate(reorder.item_ids, start=1):
        await db.execute(
            update(QueueItem)
            .where(QueueItem.id == item_id, QueueItem.venue_id == venue_id)
            .values(position=idx)
        )
    await db.commit()
    return await get_queue_by_venue(db, venue_id)


async def remove_from_queue(db: AsyncSession, venue_id: int, item_id: int) -> bool:
    """Elimina una canción de la cola (soft delete cambiando estado)."""
    result = await db.execute(
        update(QueueItem)
        .where(QueueItem.id == item_id, QueueItem.venue_id == venue_id)
        .values(status=QueueStatus.REMOVED)
    )
    await db.commit()
    return result.rowcount > 0


async def mark_as_playing(db: AsyncSession, venue_id: int, item_id: int) -> QueueItem | None:
    """Marca una canción como 'playing' y las demás como pending."""
    from datetime import datetime
    # Resetear cualquier otra que esté playing
    await db.execute(
        update(QueueItem)
        .where(QueueItem.venue_id == venue_id, QueueItem.status == QueueStatus.PLAYING)
        .values(status=QueueStatus.PLAYED, played_at=datetime.utcnow())
    )
    # Marcar la nueva como playing
    await db.execute(
        update(QueueItem)
        .where(QueueItem.id == item_id, QueueItem.venue_id == venue_id)
        .values(status=QueueStatus.PLAYING)
    )
    await db.commit()
    return await get_now_playing(db, venue_id)


async def skip_current(db: AsyncSession, venue_id: int) -> QueueItem | None:
    """Salta la canción actual y marca la siguiente como playing."""
    from datetime import datetime
    # Marcar actual como skipped
    await db.execute(
        update(QueueItem)
        .where(QueueItem.venue_id == venue_id, QueueItem.status == QueueStatus.PLAYING)
        .values(status=QueueStatus.SKIPPED, played_at=datetime.utcnow())
    )
    await db.commit()

    # Buscar la siguiente pending con menor posición
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(QueueItem.venue_id == venue_id, QueueItem.status == QueueStatus.PENDING)
        .order_by(QueueItem.position)
        .limit(1)
    )
    next_item = result.scalar_one_or_none()

    if next_item:
        next_item.status = QueueStatus.PLAYING
        await db.commit()
        await db.refresh(next_item)

    return next_item
