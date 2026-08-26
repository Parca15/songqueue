"""
Servicio de gestion de playlists.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from src.models.playlist import Playlist, PlaylistItem
from src.models.song import Song


async def get_playlists_by_venue(db: AsyncSession, venue_id: int) -> list[Playlist]:
    """Obtiene todas las playlists de un local."""
    result = await db.execute(
        select(Playlist)
        .where(Playlist.venue_id == venue_id)
        .order_by(Playlist.created_at.desc())
    )
    return result.scalars().all()


async def get_playlist_with_items(db: AsyncSession, playlist_id: int) -> Playlist | None:
    """Obtiene una playlist con sus items y canciones."""
    result = await db.execute(
        select(Playlist)
        .options(selectinload(Playlist.items).selectinload(PlaylistItem.song))
        .where(Playlist.id == playlist_id)
    )
    return result.scalar_one_or_none()


async def create_playlist(db: AsyncSession, venue_id: int, name: str) -> Playlist:
    """Crea una playlist vacia."""
    playlist = Playlist(venue_id=venue_id, name=name)
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def delete_playlist(db: AsyncSession, playlist_id: int, venue_id: int) -> bool:
    """Elimina una playlist."""
    result = await db.execute(
        select(Playlist).where(Playlist.id == playlist_id, Playlist.venue_id == venue_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        return False
    await db.delete(playlist)
    await db.commit()
    return True


async def add_song_to_playlist(db: AsyncSession, playlist_id: int, song_id: int) -> PlaylistItem | None:
    """Agrega una cancion al final de una playlist."""
    # Obtener la ultima posicion
    result = await db.execute(
        select(func.max(PlaylistItem.position)).where(PlaylistItem.playlist_id == playlist_id)
    )
    last_position = result.scalar() or 0

    item = PlaylistItem(
        playlist_id=playlist_id,
        song_id=song_id,
        position=last_position + 1,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def remove_song_from_playlist(db: AsyncSession, playlist_id: int, item_id: int) -> bool:
    """Elimina una cancion de una playlist."""
    result = await db.execute(
        select(PlaylistItem).where(
            PlaylistItem.id == item_id,
            PlaylistItem.playlist_id == playlist_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True


async def get_playlist_songs(db: AsyncSession, playlist_id: int) -> list[Song]:
    """Obtiene las canciones de una playlist ordenadas por posicion."""
    result = await db.execute(
        select(PlaylistItem)
        .options(selectinload(PlaylistItem.song))
        .where(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.position)
    )
    items = result.scalars().all()
    return [item.song for item in items if item.song]
