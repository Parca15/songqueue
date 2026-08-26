"""
Schemas para el modelo Venue.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class VenueBase(BaseModel):
    """Campos base de un Venue."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del local")
    description: str | None = Field(None, max_length=1000)


class VenueCreate(VenueBase):
    """Schema para crear un nuevo local."""
    admin_username: str = Field(..., min_length=3, max_length=100)
    admin_password: str = Field(..., min_length=6, max_length=100)
    max_songs_per_device: int = Field(default=3, ge=1, le=20)
    max_queue_size: int = Field(default=50, ge=5, le=200)
    allow_duplicates: bool = False


class VenueConfigUpdate(BaseModel):
    """Schema para actualizar configuración de un local."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    max_songs_per_device: int | None = Field(None, ge=1, le=20)
    max_queue_size: int | None = Field(None, ge=5, le=200)
    allow_duplicates: bool | None = None
    is_active: bool | None = None


class VenueResponse(VenueBase):
    """Schema de respuesta para un Venue."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    max_songs_per_device: int
    max_queue_size: int
    allow_duplicates: bool
    is_active: bool
    qr_token: str
    created_at: datetime
    updated_at: datetime
