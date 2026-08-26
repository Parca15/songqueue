"""
Servicio de gestión de dispositivos y fingerprints.
Controla el límite de canciones por dispositivo.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.models.device import Device
from src.models.queue_item import QueueItem, QueueStatus


async def get_or_create_device(
    db: AsyncSession,
    venue_id: int,
    fingerprint: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> Device:
    """Obtiene un dispositivo existente o lo crea."""
    result = await db.execute(
        select(Device).where(
            Device.venue_id == venue_id,
            Device.fingerprint == fingerprint,
        )
    )
    device = result.scalar_one_or_none()

    if device:
        # Actualizar last_seen
        from datetime import datetime
        device.last_seen = datetime.utcnow()
        if user_agent:
            device.user_agent = user_agent
        await db.commit()
        return device

    # Crear nuevo dispositivo
    device = Device(
        venue_id=venue_id,
        fingerprint=fingerprint,
        user_agent=user_agent,
        ip_address=ip_address,
        songs_in_queue=0,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def can_device_add_song(db: AsyncSession, venue_id: int, fingerprint: str, max_songs: int) -> bool:
    """Verifica si un dispositivo puede agregar más canciones."""
    result = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue_id,
            QueueItem.device_fingerprint == fingerprint,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
    )
    active_count = result.scalar() or 0
    return active_count < max_songs


async def get_device_active_count(db: AsyncSession, venue_id: int, fingerprint: str) -> int:
    """Retorna cuántas canciones activas tiene un dispositivo en la cola."""
    result = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue_id,
            QueueItem.device_fingerprint == fingerprint,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
    )
    return result.scalar() or 0
