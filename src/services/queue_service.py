"""
Servicio de gestión de colas.
Lógica de negocio para agregar, reordenar y eliminar canciones.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.queue_item import QueueItem, QueueStatus
from src.models.song import Song
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


async def get_pending_count(db: AsyncSession, venue_id: int) -> int:
    """Obtiene el número de canciones pendientes en la cola."""
    result = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.PENDING,
        )
    )
    return result.scalar() or 0


async def get_waiting_list(db: AsyncSession, venue_id: int) -> list[QueueItem]:
    """Obtiene la lista de espera (pendiente de aprobación) ordenada por llegada."""
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.WAITING,
        )
        .order_by(QueueItem.created_at)
    )
    return result.scalars().all()


async def get_waiting_count(db: AsyncSession, venue_id: int) -> int:
    """Obtiene el número de canciones en lista de espera."""
    result = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.WAITING,
        )
    )
    return result.scalar() or 0


async def approve_waiting_item(
    db: AsyncSession, venue_id: int, item_id: int, position: str = "last"
) -> QueueItem | None:
    """Aprueba un item en espera y lo pasa a la cola.

    position="first" → prioridad (primero de la cola).
    position="last" → al final de la cola.
    """
    result = await db.execute(
        select(QueueItem).where(
            QueueItem.id == item_id,
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.WAITING,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return None

    if position == "last":
        result = await db.execute(
            select(func.max(QueueItem.position)).where(
                QueueItem.venue_id == venue_id,
                QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
            )
        )
        item.position = (result.scalar() or 0) + 1

    item.status = QueueStatus.PENDING
    await db.commit()

    if position == "first":
        await move_to_position(db, venue_id, item.id, 1)

    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(QueueItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def get_last_played_genre(db: AsyncSession, venue_id: int) -> str | None:
    """Obtiene el género de la última canción reproducida en un local."""
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(
            QueueItem.venue_id == venue_id,
            QueueItem.status.in_([QueueStatus.PLAYED, QueueStatus.SKIPPED]),
        )
        .order_by(QueueItem.played_at.desc())
        .limit(1)
    )
    last_item = result.scalar_one_or_none()
    if last_item and last_item.song and last_item.song.genre:
        return last_item.song.genre
    return None


async def add_song_to_queue(
    db: AsyncSession,
    venue_id: int,
    song: Song,
    item_data: QueueItemCreate,
    status: QueueStatus = QueueStatus.PENDING,
) -> QueueItem:
    """Agrega una canción al final de la cola (o a la lista de espera).

    Los items en espera llevan position=0: su posición solo cobra sentido
    al aprobarse (primero/último), evitando colisiones con la cola real.
    """
    last_position = 0
    if status != QueueStatus.WAITING:
        # Obtener la última posición (solo items que suenan o están en cola)
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
        position=last_position + 1 if status != QueueStatus.WAITING else 0,
        status=status,
        requested_by=item_data.requested_by,
    )
    db.add(queue_item)
    await db.commit()
    await db.refresh(queue_item)
    return queue_item


async def reorder_queue(
    db: AsyncSession, venue_id: int, reorder: QueueReorder
) -> list[QueueItem]:
    """Reordena la cola según el orden de IDs proporcionado."""
    for idx, item_id in enumerate(reorder.item_ids, start=1):
        await db.execute(
            update(QueueItem)
            .where(QueueItem.id == item_id, QueueItem.venue_id == venue_id)
            .values(position=idx)
        )
    await db.commit()
    return await get_queue_by_venue(db, venue_id)


async def move_to_position(
    db: AsyncSession, venue_id: int, item_id: int, new_position: int
) -> list[QueueItem]:
    """Mueve un item a una posición específica, desplazando los demás."""
    # Obtener el item actual y su posición
    result = await db.execute(
        select(QueueItem).where(QueueItem.id == item_id, QueueItem.venue_id == venue_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return []

    old_position = item.position

    if old_position == new_position:
        return await get_queue_by_venue(db, venue_id)

    # Obtener todos los items activos ordenados por posición
    result = await db.execute(
        select(QueueItem)
        .where(
            QueueItem.venue_id == venue_id,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
        .order_by(QueueItem.position)
    )
    all_items = result.scalars().all()

    # Reconstruir el orden
    positions = []
    for qi in all_items:
        if qi.id == item_id:
            continue
        positions.append(qi)

    # Insertar en la nueva posición
    new_pos_idx = new_position - 1
    if new_pos_idx < 0:
        new_pos_idx = 0
    elif new_pos_idx >= len(positions):
        new_pos_idx = len(positions)
    positions.insert(new_pos_idx, item)

    # Asignar nuevas posiciones
    for idx, qi in enumerate(positions, start=1):
        qi.position = idx

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


async def mark_as_playing(
    db: AsyncSession, venue_id: int, item_id: int
) -> QueueItem | None:
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
