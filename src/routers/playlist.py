"""
Router para gestion de playlists.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.venue import Venue
from src.models.song import Song
from src.models.playlist import Playlist, PlaylistItem
from src.schemas.playlist import PlaylistCreate, PlaylistResponse, PlaylistItemAdd, PlaylistItemResponse
from src.services.playlist_service import (
    get_playlists_by_venue, get_playlist_with_items, create_playlist,
    delete_playlist, add_song_to_playlist, remove_song_from_playlist,
    get_playlist_songs,
)
from src.services.queue_service import add_song_to_queue, get_queue_by_venue, get_now_playing
from src.services.device_service import get_or_create_device
from src.schemas.queue import QueueItemCreate
from src.utils.auth import get_current_admin
from src.routers.websocket import manager as ws_manager
from src.routers.queue import _queue_item_to_dict, _broadcast_queue_update

router = APIRouter()


@router.get("/venue/{venue_id}", response_model=list[PlaylistResponse])
async def list_playlists(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> list[dict]:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    playlists = await get_playlists_by_venue(db, venue_id)
    result = []
    for pl in playlists:
        count_result = await db.execute(
            select(func.count(PlaylistItem.id)).where(PlaylistItem.playlist_id == pl.id)
        )
        count = count_result.scalar() or 0
        result.append({
            "id": pl.id,
            "venue_id": pl.venue_id,
            "name": pl.name,
            "created_at": pl.created_at,
            "updated_at": pl.updated_at,
            "item_count": count,
        })
    return result


@router.post("/venue/{venue_id}", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
async def create_playlist_endpoint(
    venue_id: int,
    data: PlaylistCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> dict:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    playlist = await create_playlist(db, venue_id, data.name)
    return {
        "id": playlist.id,
        "venue_id": playlist.venue_id,
        "name": playlist.name,
        "created_at": playlist.created_at,
        "updated_at": playlist.updated_at,
        "item_count": 0,
    }


@router.delete("/venue/{venue_id}/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist_endpoint(
    venue_id: int,
    playlist_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> None:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    deleted = await delete_playlist(db, playlist_id, venue_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist no encontrada")


@router.get("/venue/{venue_id}/{playlist_id}")
async def get_playlist_detail(
    venue_id: int,
    playlist_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> dict:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    playlist = await get_playlist_with_items(db, playlist_id)
    if not playlist or playlist.venue_id != venue_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist no encontrada")

    items = []
    for item in playlist.items:
        song_data = None
        if item.song:
            song_data = {
                "id": item.song.id,
                "youtube_id": item.song.youtube_id,
                "title": item.song.title,
                "channel": item.song.channel,
                "thumbnail_url": item.song.thumbnail_url,
                "duration_seconds": item.song.duration_seconds,
            }
        items.append({
            "id": item.id,
            "song_id": item.song_id,
            "position": item.position,
            "song": song_data,
        })

    return {
        "id": playlist.id,
        "venue_id": playlist.venue_id,
        "name": playlist.name,
        "created_at": playlist.created_at,
        "items": items,
    }


@router.post("/venue/{venue_id}/{playlist_id}/add", response_model=PlaylistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_to_playlist_endpoint(
    venue_id: int,
    playlist_id: int,
    data: PlaylistItemAdd,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> dict:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    # Verificar que la playlist existe y pertenece al local
    playlist = await get_playlist_with_items(db, playlist_id)
    if not playlist or playlist.venue_id != venue_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist no encontrada")

    # Verificar que la cancion existe
    song_result = await db.execute(select(Song).where(Song.id == data.song_id))
    song = song_result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancion no encontrada")

    item = await add_song_to_playlist(db, playlist_id, data.song_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al agregar cancion")

    return {
        "id": item.id,
        "playlist_id": item.playlist_id,
        "song_id": item.song_id,
        "position": item.position,
        "song": {
            "id": song.id,
            "youtube_id": song.youtube_id,
            "title": song.title,
            "channel": song.channel,
            "thumbnail_url": song.thumbnail_url,
            "duration_seconds": song.duration_seconds,
        },
        "created_at": item.created_at,
    }


@router.delete("/venue/{venue_id}/{playlist_id}/item/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_playlist_endpoint(
    venue_id: int,
    playlist_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> None:
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    removed = await remove_song_from_playlist(db, playlist_id, item_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")


@router.post("/venue/{venue_id}/{playlist_id}/play")
async def play_playlist_endpoint(
    venue_id: int,
    playlist_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> dict:
    """Agrega todas las canciones de una playlist a la cola actual."""
    if current_admin.id != venue_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    songs = await get_playlist_songs(db, playlist_id)
    if not songs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist vacia o no encontrada")

    added_count = 0
    for song in songs:
        try:
            queue_data = QueueItemCreate(
                youtube_id=song.youtube_id,
                device_fingerprint="playlist-system",
                requested_by="Playlist",
                title=song.title,
                channel=song.channel,
                thumbnail_url=song.thumbnail_url,
                duration_seconds=song.duration_seconds,
            )
            await get_or_create_device(db, venue_id, "playlist-system")
            await add_song_to_queue(db, venue_id, song, queue_data)
            added_count += 1
        except Exception:
            continue

    await _broadcast_queue_update(db, venue_id)

    return {"added": added_count, "total": len(songs)}


from sqlalchemy import func
