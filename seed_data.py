"""
Script para poblar la base de datos con datos de prueba.
Ejecutar: python seed_data.py
"""
import asyncio
from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal, init_db
from src.models.venue import Venue
from src.models.song import Song
from src.models.queue_item import QueueItem, QueueStatus
from src.models.device import Device
from src.utils.security import get_password_hash


async def clear_existing_data(db: AsyncSession) -> None:
    """Limpia los datos existentes para evitar duplicados."""
    print("Limpiando datos existentes...")
    await db.execute(delete(QueueItem))
    await db.execute(delete(Device))
    await db.execute(delete(Song))
    await db.execute(delete(Venue))
    # Resetear AUTO_INCREMENT en MySQL
    await db.execute(text("ALTER TABLE venues AUTO_INCREMENT = 1"))
    await db.execute(text("ALTER TABLE songs AUTO_INCREMENT = 1"))
    await db.execute(text("ALTER TABLE queue_items AUTO_INCREMENT = 1"))
    await db.execute(text("ALTER TABLE devices AUTO_INCREMENT = 1"))
    await db.commit()
    print("Datos limpiados")


async def seed_venues(db: AsyncSession) -> list[Venue]:
    """Crea locales de prueba."""
    venues_data = [
        {
            "name": "Bar La Esquina",
            "slug": "bar-la-esquina",
            "description": "El mejor bar del barrio con musica en vivo",
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
            "name": "Cafe del Jazz",
            "slug": "cafe-del-jazz",
            "description": "Ambiente relajado con la mejor seleccion musical",
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
    print(f"Creados {len(venues)} locales")
    return venues


async def seed_songs(db: AsyncSession) -> list[Song]:
    """Crea canciones de prueba."""
    songs_data = [
        {
            "youtube_id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
            "channel": "Rick Astley",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
            "duration_seconds": 213,
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
            "title": "Ed Sheeran - Shape of You (Official Music Video)",
            "channel": "Ed Sheeran",
            "thumbnail_url": "https://i.ytimg.com/vi/JGwWNGJdvx8/mqdefault.jpg",
            "duration_seconds": 263,
        },
        {
            "youtube_id": "9bZkp7q19f0",
            "title": "PSY - GANGNAM STYLE",
            "channel": "officialpsy",
            "thumbnail_url": "https://i.ytimg.com/vi/9bZkp7q19f0/mqdefault.jpg",
            "duration_seconds": 252,
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
    print(f"Creadas {len(songs)} canciones")
    return songs


async def seed_queue(db: AsyncSession, venues: list[Venue], songs: list[Song]) -> None:
    """Crea items de cola de prueba."""
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
    print(f"Creados {len(queue_items)} items en cola")


async def main() -> None:
    """Ejecuta el seeding completo. Usa --force para recrear datos existentes."""
    import sys

    force = "--force" in sys.argv
    print("Iniciando seed de datos...")

    async with AsyncSessionLocal() as db:
        await init_db()

        # Verificar si ya hay datos
        result = await db.execute(select(Venue).limit(1))
        existing = result.scalar_one_or_none()

        if existing and not force:
            print("Ya existen datos en la BD. Usar --force para recrear.")
            return

        if force:
            await clear_existing_data(db)

        venues = await seed_venues(db)
        songs = await seed_songs(db)
        await seed_queue(db, venues, songs)

    print("")
    print("Seed completado exitosamente!")
    print("")
    print("Datos de prueba:")
    print(f"   Locales: {len(venues)}")
    print(f"   Canciones: {len(songs)}")
    print("")
    print("Credenciales de admin:")
    for v in venues:
        print(f"   {v.name} (ID: {v.id}): {v.admin_username} / ***")
    print("")
    print("URLs correctas (usa el ID que aparece arriba):")
    for v in venues:
        print(f"   {v.name}: http://localhost:8000/static/admin.html?venue={v.id}")


if __name__ == "__main__":
    asyncio.run(main())
