"""
Schemas para Playlist y PlaylistItem.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PlaylistCreate(BaseModel):
    """Schema para crear una playlist."""
    name: str = Field(..., min_length=1, max_length=255)


class PlaylistResponse(BaseModel):
    """Schema de respuesta para una playlist."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    name: str
    created_at: datetime
    updated_at: datetime
    item_count: int = 0


class PlaylistItemAdd(BaseModel):
    """Schema para agregar una cancion a una playlist."""
    song_id: int = Field(..., gt=0)


class PlaylistItemResponse(BaseModel):
    """Schema de respuesta para un item de playlist."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    playlist_id: int
    song_id: int
    position: int
    song: dict | None = None
    created_at: datetime
