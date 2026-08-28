"""
Schemas para el modelo Song.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SongBase(BaseModel):
    """Campos base de una canción."""
    youtube_id: str = Field(..., min_length=5, max_length=20, description="ID del video de YouTube")
    title: str = Field(..., min_length=1, max_length=500)


class SongCreate(SongBase):
    """Schema para crear una canción."""
    channel: str | None = Field(None, max_length=255)
    thumbnail_url: str | None = Field(None, max_length=1000)
    duration_seconds: int | None = Field(None, ge=1)
    genre: str | None = Field(None, max_length=100)


class SongResponse(SongBase):
    """Schema de respuesta para una canción."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str | None
    thumbnail_url: str | None
    duration_seconds: int | None
    genre: str | None
    created_at: datetime


class YouTubeSearchResult(BaseModel):
    """Resultado de búsqueda en YouTube."""
    youtube_id: str
    title: str
    channel: str
    thumbnail_url: str
    duration_seconds: int | None = None
    genre: str | None = None
    views: int | None = None
