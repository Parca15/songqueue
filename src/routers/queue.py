"""
Router para gestión de colas de canciones.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.venue import Venue
from src.models.song import Song
from src.models.queue_item import QueueItem, QueueStatus
from src.schemas.queue import QueueItemCreate, QueueItemResponse, QueueReorder, QueueState
from src.services.queue_service import (
    get_queue_by_venue,
    get_now_playing,
    add_song_to_queue,
    reorder_queue,
    remove_from_queue,
    mark_as_playing,
    skip_current,
)
from src.services.device_service import can_device_add_song, get_or_create_device
from src.services.youtube_service import get_video_details

router = APIRouter()


def _queue_item_to_dict(item: QueueItem) -> dict:
    """Convierte un QueueItem a dict con la canción anidada."""
    song_dict = None
    if item.song:
        song_dict = {
            "id": item.song.id,
            "youtube_id": item.song.youtube_id,
            "title": item.song.title,
            "channel": item.song.channel,
            "thumbnail_url": item.song.thumbnail_url,
            "duration_seconds": item.song.duration_seconds,
            "created_at": item.song.created_at.isoformat() if item.song.created_at else None,
        }
    return {
        "id": item.id,
        "venue_id": item.venue_id,
        "song_id": item.song_id,
        "position": item.position,
        "status": item.status.value if hasattr(item.status, 'value') else item.status,
        "requested_by": item.requested_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "song": song_dict,
    }


@router.get("/venue/{venue_id}", response_model=QueueState)
async def get_queue_state(venue_id: int, db: AsyncSession = Depends(get_db)) -> QueueState:
    """Obtiene el estado completo de la cola de un local."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")

    now_playing = await get_now_playing(db, venue_id)
    queue = await get_queue_by_venue(db, venue_id)

    # Filtrar now_playing de upcoming
    upcoming = [q for q in queue if q.status != QueueStatus.PLAYING]

    return QueueState(
        venue_id=venue_id,
        now_playing=_queue_item_to_dict(now_playing) if now_playing else None,
        upcoming=[_queue_item_to_dict(q) for q in upcoming],
        total_pending=len(upcoming),
    )


@router.post("/venue/{venue_id}/add", response_model=QueueItemResponse, status_code=status.HTTP_201_CREATED)
async def add_to_queue(
    venue_id: int,
    item_data: QueueItemCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Agrega una canción a la cola de un local."""
    # Verificar local
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue or not venue.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado o inactivo")

    # Verificar límite del dispositivo
    can_add = await can_device_add_song(db, venue_id, item_data.device_fingerprint, venue.max_songs_per_device)
    if not can_add:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Límite de {venue.max_songs_per_device} canciones por dispositivo alcanzado",
        )

    # Obtener o crear canción
    result = await db.execute(select(Song).where(Song.youtube_id == item_data.youtube_id))
    song = result.scalar_one_or_none()

    if not song:
        # Buscar en YouTube y crear
        details = await get_video_details(item_data.youtube_id)
        if not details:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video de YouTube no encontrado")
        song = Song(
            youtube_id=details.youtube_id,
            title=details.title,
            channel=details.channel,
            thumbnail_url=details.thumbnail_url,
            duration_seconds=details.duration_seconds,
        )
        db.add(song)
        await db.commit()
        await db.refresh(song)

    # Verificar duplicados
    if not venue.allow_duplicates:
        result = await db.execute(
            select(QueueItem).where(
                QueueItem.venue_id == venue_id,
                QueueItem.song_id == song.id,
                QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta canción ya está en la cola",
            )

    # Verificar tamaño máximo de cola
    result = await db.execute(
        select(QueueItem).where(
            QueueItem.venue_id == venue_id,
            QueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PLAYING]),
        )
    )
    if len(result.scalars().all()) >= venue.max_queue_size:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cola llena (máximo {venue.max_queue_size} canciones)",
        )

    # Registrar/actualizar dispositivo
    await get_or_create_device(db, venue_id, item_data.device_fingerprint)

    # Agregar a cola
    queue_item = await add_song_to_queue(db, venue_id, song, item_data)

    # Recargar con la relación song
    result = await db.execute(
        select(QueueItem)
        .options(selectinload(QueueItem.song))
        .where(QueueItem.id == queue_item.id)
    )
    queue_item = result.scalar_one()

    return _queue_item_to_dict(queue_item)


@router.post("/venue/{venue_id}/reorder")
async def reorder_queue_endpoint(
    venue_id: int,
    reorder: QueueReorder,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Reordena la cola (solo admin)."""
    items = await reorder_queue(db, venue_id, reorder)
    return [_queue_item_to_dict(item) for item in items]


@router.delete("/venue/{venue_id}/item/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_queue_item(
    venue_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Elimina una canción de la cola (solo admin)."""
    removed = await remove_from_queue(db, venue_id, item_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")


@router.post("/venue/{venue_id}/play/{item_id}")
async def play_item(
    venue_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Marca una canción como playing (admin o reproductor)."""
    item = await mark_as_playing(db, venue_id, item_id)
    if item:
        result = await db.execute(
            select(QueueItem)
            .options(selectinload(QueueItem.song))
            .where(QueueItem.id == item.id)
        )
        item = result.scalar_one()
    return _queue_item_to_dict(item) if item else None


@router.post("/venue/{venue_id}/skip")
async def skip_item(venue_id: int, db: AsyncSession = Depends(get_db)) -> dict | None:
    """Salta la canción actual y pasa a la siguiente."""
    next_item = await skip_current(db, venue_id)
    if next_item:
        result = await db.execute(
            select(QueueItem)
            .options(selectinload(QueueItem.song))
            .where(QueueItem.id == next_item.id)
        )
        next_item = result.scalar_one()
    return _queue_item_to_dict(next_item) if next_item else None
