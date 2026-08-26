"""
Schemas para el modelo QueueItem.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from src.models.queue_item import QueueStatus


class QueueItemBase(BaseModel):
    """Campos base de un item de cola."""
    song_id: int = Field(..., gt=0)
    requested_by: str | None = Field(None, max_length=100)


class QueueItemCreate(BaseModel):
    """Schema para agregar una canción a la cola."""
    youtube_id: str = Field(..., min_length=1, max_length=20)
    requested_by: str | None = Field(None, max_length=100)
    device_fingerprint: str = Field(..., min_length=10, max_length=128)
    title: str | None = Field(None, max_length=500)
    channel: str | None = Field(None, max_length=255)
    thumbnail_url: str | None = Field(None, max_length=1000)
    duration_seconds: int | None = Field(None, ge=1)
    genre: str | None = Field(None, max_length=100)


class QueueItemResponse(BaseModel):
    """Schema de respuesta para un item de cola."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    song_id: int
    position: int
    status: QueueStatus
    requested_by: str | None
    created_at: datetime
    song: dict  # Se populará con SongResponse


class QueueReorder(BaseModel):
    """Schema para reordenar la cola."""
    item_ids: list[int] = Field(..., min_length=1, description="IDs de items en el nuevo orden")


class QueueMoveToPosition(BaseModel):
    """Schema para mover un item a una posición específica."""
    item_id: int
    new_position: int = Field(..., ge=1, description="Nueva posición (1 = primero)")


class QueueState(BaseModel):
    """Estado completo de la cola de un local."""
    venue_id: int
    now_playing: QueueItemResponse | None
    upcoming: list[QueueItemResponse]
    total_pending: int
