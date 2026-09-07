"""
Router para gestión de canciones y búsqueda en YouTube.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.song import Song
from src.schemas.song import SongCreate, SongResponse, YouTubeSearchResult
from src.services.youtube_service import get_video_details, search_youtube
from src.utils.rate_limit import limiter

router = APIRouter()


@router.get("/search", response_model=list[YouTubeSearchResult])
@limiter.limit("60/minute")
async def search_songs(
    request: Request,
    q: str = Query(
        ..., min_length=1, max_length=200, description="Término de búsqueda"
    ),
    limit: int = Query(10, ge=1, le=50),
) -> list[YouTubeSearchResult]:
    """Busca canciones en YouTube (limitado: protege la cuota de la API)."""
    return await search_youtube(q, max_results=limit)


@router.get("/youtube/{youtube_id}", response_model=YouTubeSearchResult)
async def get_song_details(youtube_id: str) -> YouTubeSearchResult:
    """Obtiene detalles de un video de YouTube por su ID."""
    details = await get_video_details(youtube_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado"
        )
    return details


@router.post("", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
async def create_song(
    song_data: SongCreate,
    db: AsyncSession = Depends(get_db),
) -> Song:
    """Crea/Registra una canción en la base de datos."""
    # Verificar si ya existe
    result = await db.execute(
        select(Song).where(Song.youtube_id == song_data.youtube_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    song = Song(**song_data.model_dump())
    db.add(song)
    await db.commit()
    await db.refresh(song)
    return song


@router.get("/{song_id}", response_model=SongResponse)
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)) -> Song:
    """Obtiene una canción por su ID interno."""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Canción no encontrada"
        )
    return song
