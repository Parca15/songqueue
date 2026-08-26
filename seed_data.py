"""
Script para poblar la base de datos con datos de prueba.
Ejecutar: python seed_data.py
"""
import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal, engine, init_db
from src.models.venue import Venue
from src.models.song import Song
from src.models.queue_item import QueueItem, QueueStatus
from src.utils.security import get_password_hash


async def seed_venues(db: AsyncSession) -> list[Venue]:
    """Crea locales de prueba."""
    existing = (await db.execute(select(Venue))).scalars().all()
    if existing:
        print(f"⚠️ Ya existen {len(existing)} locales. Se reutilizan los datos existentes.")
        return list(existing)

    venues_data = [
        {
            "name": "Bar La Esquina",
            "slug": "bar-la-esquina",
            "description": "El mejor bar del barrio con música en vivo",
            "max_songs_per_device": 3,
            "max_queue_size": 30,
            "allow_duplicates": False,
            "admin_username": "admin_esquina",
            "admin_password_hash": get_password_hash("esquina123"),
        },
        {
            "name": "Karaoke Night Club",
            "slug": "karaoke-night-club",
            "description": "Karaoke todas las noches hasta las 4am",
            "max_songs_per_device": 5,
            "max_queue_size": 50,
            "allow_duplicates": True,
            "admin_username": "admin_karaoke",
            "admin_password_hash": get_password_hash("karaoke123"),
        },
        {
            "name": "Café del Jazz",
            "slug": "cafe-del-jazz",
            "description": "Ambiente relajado con la mejor selección musical",
            "max_songs_per_device": 2,
            "max_queue_size": 20,
            "allow_duplicates": False,
            "admin_username": "admin_jazz",
            "admin_password_hash": get_password_hash("jazz123"),
        },
    ]

    venues = []
    for data in venues_data:
        venue = Venue(**data)
        db.add(venue)
        venues.append(venue)

    await db.commit()
    for v in venues:
        await db.refresh(v)
    print(f"✅ Creados {len(venues)} locales")
    return venues


async def seed_songs(db: AsyncSession) -> list[Song]:
    """Crea canciones de prueba (videos populares de YouTube)."""
    existing = (await db.execute(select(Song))).scalars().all()
    if existing:
        print(f"⚠️ Ya existen {len(existing)} canciones. Se reutilizan los datos existentes.")
        return list(existing)

    songs_data = [
        {
            "youtube_id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up",
            "channel": "Rick Astley",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
            "duration_seconds": 213,
        },
        {
            "youtube_id": "9bZkp7q19f0",
            "title": "PSY - GANGNAM STYLE",
            "channel": "officialpsy",
            "thumbnail_url": "https://i.ytimg.com/vi/9bZkp7q19f0/mqdefault.jpg",
            "duration_seconds": 252,
        },
        {
            "youtube_id": "kJQP7kiw5Fk",
            "title": "Luis Fonsi - Despacito ft. Daddy Yankee",
            "channel": "LuisFonsiVEVO",
            "thumbnail_url": "https://i.ytimg.com/vi/kJQP7kiw5Fk/mqdefault.jpg",
            "duration_seconds": 282,
        },
        {
            "youtube_id": "JGwWNGJdvx8",
            "title": "Ed Sheeran - Shape of You",
            "channel": "Ed Sheeran",
            "thumbnail_url": "https://i.ytimg.com/vi/JGwWNGJdvx8/mqdefault.jpg",
            "duration_seconds": 263,
        },
        {
            "youtube_id": "RgKAFK5djSk",
            "title": "Wiz Khalifa - See You Again ft. Charlie Puth",
            "channel": "Wiz Khalifa",
            "thumbnail_url": "https://i.ytimg.com/vi/RgKAFK5djSk/mqdefault.jpg",
            "duration_seconds": 229,
        },
    ]

    songs = []
    for data in songs_data:
        song = Song(**data)
        db.add(song)
        songs.append(song)

    await db.commit()
    for s in songs:
        await db.refresh(s)
    print(f"✅ Creadas {len(songs)} canciones")
    return songs


async def seed_queue(db: AsyncSession, venues: list[Venue], songs: list[Song]) -> None:
    """Crea items de cola de prueba."""
    existing = (await db.execute(select(QueueItem))).scalars().all()
    if existing:
        print(f"⚠️ Ya existen {len(existing)} items en cola. Se reutilizan los datos existentes.")
        return

    queue_items = [
        {
            "venue_id": venues[0].id,
            "song_id": songs[0].id,
            "device_fingerprint": "fp_device_001_abc123",
            "position": 1,
            "status": QueueStatus.PLAYING,
            "requested_by": "Juanito",
        },
        {
            "venue_id": venues[0].id,
            "song_id": songs[1].id,
            "device_fingerprint": "fp_device_002_def456",
            "position": 2,
            "status": QueueStatus.PENDING,
            "requested_by": "Maria",
        },
        {
            "venue_id": venues[0].id,
            "song_id": songs[2].id,
            "device_fingerprint": "fp_device_001_abc123",
            "position": 3,
            "status": QueueStatus.PENDING,
            "requested_by": "Juanito",
        },
        {
            "venue_id": venues[1].id,
            "song_id": songs[3].id,
            "device_fingerprint": "fp_device_003_ghi789",
            "position": 1,
            "status": QueueStatus.PENDING,
            "requested_by": "Pedro",
        },
        {
            "venue_id": venues[1].id,
            "song_id": songs[4].id,
            "device_fingerprint": "fp_device_004_jkl012",
            "position": 2,
            "status": QueueStatus.PENDING,
            "requested_by": "Ana",
        },
    ]

    for data in queue_items:
        item = QueueItem(**data)
        db.add(item)

    await db.commit()
    print(f"✅ Creados {len(queue_items)} items en cola")


async def main() -> None:
    """Ejecuta el seeding completo."""
    print("🌱 Iniciando seed de datos...")

    try:
        async with AsyncSessionLocal() as db:
            # Crear tablas si no existen (modo dev)
            await init_db()

            venues = await seed_venues(db)
            songs = await seed_songs(db)
            await seed_queue(db, venues, songs)
    finally:
        await engine.dispose()

    print("🎉 Seed completado exitosamente!")
    print("\n📋 Datos de prueba:")
    print(f"   • Locales: {len(venues)}")
    print(f"   • Canciones: {len(songs)}")
    print("\n🔑 Credenciales de admin:")
    print("   • Bar La Esquina: admin_esquina / esquina123")
    print("   • Karaoke Night Club: admin_karaoke / karaoke123")
    print("   • Café del Jazz: admin_jazz / jazz123")


if __name__ == "__main__":
    asyncio.run(main())
