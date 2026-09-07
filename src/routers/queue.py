"""
Router para gestión de colas de canciones.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.queue_item import QueueItem, QueueStatus
from src.models.song import Song
from src.models.venue import Venue
from src.routers.websocket import manager as ws_manager
from src.schemas.queue import (
    QueueItemCreate,
    QueueItemResponse,
    QueueMoveToPosition,
    QueueReorder,
    QueueState,
    WaitingApprove,
)
from src.services.device_service import can_device_add_song, get_or_create_device
from src.services.queue_service import (
    add_song_to_queue,
    approve_waiting_item,
    get_now_playing,
    get_queue_by_venue,
    get_waiting_list,
    mark_as_playing,
    move_to_position,
    remove_from_queue,
    reorder_queue,
    skip_current,
)
from src.services.youtube_service import get_video_details
from src.utils.auth import Principal, get_current_principal, require_venue_access
from src.utils.rate_limit import limiter

router = APIRouter()

# Fingerprints del sistema que siempre entran directo a la cola (sin aprobación)
_SYSTEM_FINGERPRINTS = ("auto-play-system", "playlist-system")

# Locks por local para el alta de canciones: las validaciones (límite por
# dispositivo, duplicados, tamaño) y el INSERT deben ser atómicos. Válido
# para despliegue de 1 réplica, igual que el ConnectionManager del WS.
_add_locks: dict[int, asyncio.Lock] = {}


def _add_lock(venue_id: int) -> asyncio.Lock:
    lock = _add_locks.get(venue_id)
    if lock is None:
        lock = asyncio.Lock()
        _add_locks[venue_id] = lock
    return lock


def _is_system_request(fingerprint: str) -> bool:
    return fingerprint in _SYSTEM_FINGERPRINTS or fingerprint.startswith("admin-venue-")


# Guard anti-duplicado para auto-skip: evita que llamadas concurrentes/duplicadas
# de varios reproductores consuman varias canciones de la cola a la vez.
_auto_skip_in_flight: set[int] = set()


def _queue_item_to_dict(item: QueueItem) -> dict:
    song_dict = None
    if item.song:
        song_dict = {
            "id": item.song.id,
            "youtube_id": item.song.youtube_id,
            "title": item.song.title,
            "channel": item.song.channel,
            "thumbnail_url": item.song.thumbnail_url,
            "duration_seconds": item.song.duration_seconds,
            "created_at": (
                item.song.created_at.isoformat() if item.song.created_at else None
            ),
        }
    return {
        "id": item.id,
        "venue_id": item.venue_id,
        "song_id": item.song_id,
        "position": item.position,
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "requested_by": item.requested_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "song": song_dict,
    }


async def _broadcast_queue_update(db: AsyncSession, venue_id: int):
    """Broadcast del estado actual de la cola a todos los clientes del local."""
    now_playing = await get_now_playing(db, venue_id)
    queue = await get_queue_by_venue(db, venue_id)
    upcoming = [q for q in queue if q.status != QueueStatus.PLAYING]

    await ws_manager.broadcast_to_venue(
        venue_id,
        {
            "type": "queue_updated",
            "data": {
                "venue_id": venue_id,
                "now_playing": (
                    _queue_item_to_dict(now_playing) if now_playing else None
                ),
                "upcoming": [_queue_item_to_dict(q) for q in upcoming],
                "total_pending": len(upcoming),
            },
        },
    )


async def _broadcast_waiting_update(db: AsyncSession, venue_id: int):
    """Broadcast de la lista de espera solo a los admins del local."""
    waiting = await get_waiting_list(db, venue_id)

    await ws_manager.send_to_admins(
        venue_id,
        {
            "type": "waiting_updated",
            "data": {
                "venue_id": venue_id,
                "waiting": [_queue_item_to_dict(q) for q in waiting],
                "total_waiting": len(waiting),
            },
        },
    )


@router.get("/venue/{venue_id}", response_model=QueueState)
async def get_queue_state(
    venue_id: int, db: AsyncSession = Depends(get_db)
) -> QueueState:
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )

    now_playing = await get_now_playing(db, venue_id)
    queue = await get_queue_by_venue(db, venue_id)
    upcoming = [q for q in queue if q.status != QueueStatus.PLAYING]

    return QueueState(
        venue_id=venue_id,
        now_playing=_queue_item_to_dict(now_playing) if now_playing else None,
        upcoming=[_queue_item_to_dict(q) for q in upcoming],
        total_pending=len(upcoming),
    )


@router.post(
    "/venue/{venue_id}/add",
    response_model=QueueItemResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_to_queue(
    request: Request,
    venue_id: int,
    item_data: QueueItemCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue or not venue.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local no encontrado o inactivo",
        )

    result = await db.execute(
        select(Song).where(Song.youtube_id == item_data.youtube_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        # Usar metadata del request si esta disponible
        if item_data.title:
            song = Song(
                youtube_id=item_data.youtube_id,
                title=item_data.title,
                channel=item_data.channel or "Unknown",
                thumbnail_url=item_data.thumbnail_url or "",
                duration_seconds=item_data.duration_seconds,
                genre=item_data.genre,
            )
            db.add(song)
            try:
                await db.commit()
                await db.refresh(song)
            except IntegrityError:
                # Carrera: otro request creó la misma canción a la vez
                await db.rollback()
                result = await db.execute(
                    select(Song).where(Song.youtube_id == song.youtube_id)
                )
                song = result.scalar_one()
        else:
            details = await get_video_details(item_data.youtube_id)
            if not details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video de YouTube no encontrado",
                )
            song = Song(
                youtube_id=details.youtube_id,
                title=details.title,
                channel=details.channel,
                thumbnail_url=details.thumbnail_url,
                duration_seconds=details.duration_seconds,
                genre=details.genre,
            )
            db.add(song)
            try:
                await db.commit()
                await db.refresh(song)
            except IntegrityError:
                # Carrera: otro request creó la misma canción a la vez
                await db.rollback()
                result = await db.execute(
                    select(Song).where(Song.youtube_id == song.youtube_id)
                )
                song = result.scalar_one()

    # Sección crítica por local: validaciones (cupo, duplicados, tamaño)
    # e INSERT atómicos bajo lock (despliegue de 1 réplica).
    async with _add_lock(venue_id):
        can_add = await can_device_add_song(
            db, venue_id, item_data.device_fingerprint, venue.max_songs_per_device
        )
        if not can_add:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Límite de {venue.max_songs_per_device} canciones por dispositivo alcanzado",
            )

        if not venue.allow_duplicates:
            result = await db.execute(
                select(QueueItem).where(
                    QueueItem.venue_id == venue_id,
                    QueueItem.song_id == song.id,
                    QueueItem.status.in_(
                        [QueueStatus.PENDING, QueueStatus.PLAYING, QueueStatus.WAITING]
                    ),
                )
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Esta canción ya está en la cola",
                )

        result = await db.execute(
            select(func.count(QueueItem.id)).where(
                QueueItem.venue_id == venue_id,
                QueueItem.status.in_(
                    [QueueStatus.PENDING, QueueStatus.PLAYING, QueueStatus.WAITING]
                ),
            )
        )
        if (result.scalar() or 0) >= venue.max_queue_size:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cola llena (máximo {venue.max_queue_size} canciones)",
            )

        await get_or_create_device(db, venue_id, item_data.device_fingerprint)

        # Si el local requiere aprobación y es un cliente humano → lista de espera
        to_waiting = venue.require_approval and not _is_system_request(
            item_data.device_fingerprint
        )
        queue_item = await add_song_to_queue(
            db,
            venue_id,
            song,
            item_data,
            status=QueueStatus.WAITING if to_waiting else QueueStatus.PENDING,
        )

        # Si el item fue agregado por un cliente directo a cola (no auto-play/playlist),
        # dar prioridad: insertar antes del primer item de auto-play/playlist
        if not to_waiting and item_data.device_fingerprint not in _SYSTEM_FINGERPRINTS:
            # Obtener la cola actual
            current_queue = await get_queue_by_venue(db, venue_id)
            if current_queue:
                # Encontrar el primer item de playlist/auto-play
                first_system_idx = None
                for idx, qi in enumerate(current_queue):
                    if qi.device_fingerprint in ("auto-play-system", "playlist-system"):
                        first_system_idx = idx
                        break

                if (
                    first_system_idx is not None
                    and queue_item.id != current_queue[first_system_idx].id
                ):
                    # Mover el item del cliente a la posicion del primer item del sistema
                    from src.services.queue_service import move_to_position

                    await move_to_position(
                        db, venue_id, queue_item.id, first_system_idx + 1
                    )
                    # Recargar el item
                    result = await db.execute(
                        select(QueueItem)
                        .options(selectinload(QueueItem.song))
                        .where(QueueItem.id == queue_item.id)
                    )
                    queue_item = result.scalar_one()

        result = await db.execute(
            select(QueueItem)
            .options(selectinload(QueueItem.song))
            .where(QueueItem.id == queue_item.id)
        )
        queue_item = result.scalar_one()

    # Broadcast automático
    await _broadcast_queue_update(db, venue_id)
    if to_waiting:
        await _broadcast_waiting_update(db, venue_id)

    return _queue_item_to_dict(queue_item)


@router.get("/venue/{venue_id}/waiting")
async def get_waiting_state(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict:
    """Lista de espera completa (solo admin del local)."""
    require_venue_access(current_admin, venue_id)

    waiting = await get_waiting_list(db, venue_id)
    return {
        "venue_id": venue_id,
        "waiting": [_queue_item_to_dict(q) for q in waiting],
        "total_waiting": len(waiting),
    }


@router.get("/venue/{venue_id}/waiting/mine")
async def get_my_waiting(
    venue_id: int,
    device_fingerprint: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Canciones en espera de un dispositivo (público, para que el cliente vea las suyas)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )

    waiting = await get_waiting_list(db, venue_id)
    mine = [q for q in waiting if q.device_fingerprint == device_fingerprint]
    return {
        "venue_id": venue_id,
        "waiting": [_queue_item_to_dict(q) for q in mine],
        "total_waiting": len(mine),
    }


@router.post("/venue/{venue_id}/waiting/{item_id}/approve")
async def approve_waiting(
    venue_id: int,
    item_id: int,
    approval: WaitingApprove,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict:
    """Aprueba un item en espera y lo pasa a la cola (primero o último)."""
    require_venue_access(current_admin, venue_id)

    item = await approve_waiting_item(db, venue_id, item_id, approval.position)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado en espera"
        )

    await _broadcast_queue_update(db, venue_id)
    await _broadcast_waiting_update(db, venue_id)
    return _queue_item_to_dict(item)


@router.post(
    "/venue/{venue_id}/waiting/{item_id}/reject", status_code=status.HTTP_200_OK
)
async def reject_waiting(
    venue_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict:
    """Rechaza un item en espera (lo descarta)."""
    require_venue_access(current_admin, venue_id)

    result = await db.execute(
        select(QueueItem).where(
            QueueItem.id == item_id,
            QueueItem.venue_id == venue_id,
            QueueItem.status == QueueStatus.WAITING,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado en espera"
        )

    await remove_from_queue(db, venue_id, item_id)

    await _broadcast_queue_update(db, venue_id)
    await _broadcast_waiting_update(db, venue_id)
    return {"ok": True, "item_id": item_id}


@router.post("/venue/{venue_id}/reorder")
async def reorder_queue_endpoint(
    venue_id: int,
    reorder: QueueReorder,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> list[dict]:
    require_venue_access(current_admin, venue_id)

    items = await reorder_queue(db, venue_id, reorder)
    await _broadcast_queue_update(db, venue_id)
    return [_queue_item_to_dict(item) for item in items]


@router.post("/venue/{venue_id}/move")
async def move_queue_item(
    venue_id: int,
    move_data: QueueMoveToPosition,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> list[dict]:
    require_venue_access(current_admin, venue_id)

    items = await move_to_position(
        db, venue_id, move_data.item_id, move_data.new_position
    )
    await _broadcast_queue_update(db, venue_id)
    return [_queue_item_to_dict(item) for item in items]


@router.delete(
    "/venue/{venue_id}/item/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_queue_item(
    venue_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> None:
    require_venue_access(current_admin, venue_id)

    removed = await remove_from_queue(db, venue_id, item_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado"
        )

    await _broadcast_queue_update(db, venue_id)


@router.post("/venue/{venue_id}/play/{item_id}")
async def play_item(
    venue_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict | None:
    require_venue_access(current_admin, venue_id)

    item = await mark_as_playing(db, venue_id, item_id)
    if item:
        result = await db.execute(
            select(QueueItem)
            .options(selectinload(QueueItem.song))
            .where(QueueItem.id == item.id)
        )
        item = result.scalar_one()

    await _broadcast_queue_update(db, venue_id)

    # Notificar al reproductor
    if item:
        await ws_manager.send_to_player(
            venue_id,
            {
                "type": "play_song",
                "data": _queue_item_to_dict(item),
            },
        )

    return _queue_item_to_dict(item) if item else None


@router.post("/venue/{venue_id}/skip")
async def skip_item(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict | None:
    require_venue_access(current_admin, venue_id)

    next_item = await skip_current(db, venue_id)
    if next_item:
        result = await db.execute(
            select(QueueItem)
            .options(selectinload(QueueItem.song))
            .where(QueueItem.id == next_item.id)
        )
        next_item = result.scalar_one()

    await _broadcast_queue_update(db, venue_id)

    if next_item:
        await ws_manager.send_to_player(
            venue_id,
            {
                "type": "play_song",
                "data": _queue_item_to_dict(next_item),
            },
        )

    return _queue_item_to_dict(next_item) if next_item else None


@router.post("/venue/{venue_id}/auto-skip")
@limiter.limit("20/minute")
async def auto_skip_item(
    request: Request,
    venue_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Auto-skip cuando termina una cancion. No requiere autenticacion.

    Protegido contra llamadas duplicadas/concurrentes: si ya hay un auto-skip
    en curso para el local, se ignora para no saltar varias canciones a la vez.
    """
    if venue_id in _auto_skip_in_flight:
        return None
    _auto_skip_in_flight.add(venue_id)
    try:
        next_item = await skip_current(db, venue_id)
        if next_item:
            result = await db.execute(
                select(QueueItem)
                .options(selectinload(QueueItem.song))
                .where(QueueItem.id == next_item.id)
            )
            next_item = result.scalar_one()

        await _broadcast_queue_update(db, venue_id)

        if next_item:
            await ws_manager.send_to_player(
                venue_id,
                {
                    "type": "play_song",
                    "data": _queue_item_to_dict(next_item),
                },
            )

        return _queue_item_to_dict(next_item) if next_item else None
    finally:
        _auto_skip_in_flight.discard(venue_id)
