"""
Schemas para el modelo Venue.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VenueBase(BaseModel):
    """Campos base de un Venue."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre del local")
    description: str | None = Field(None, max_length=1000)


class VenueCreate(VenueBase):
    """Schema para crear un nuevo local."""

    admin_username: str = Field(..., min_length=3, max_length=100)
    admin_password: str = Field(
        ...,
        min_length=6,
        max_length=71,
        description="Max 71 caracteres por limitacion de bcrypt",
    )
    max_songs_per_device: int = Field(default=3, ge=1, le=20)
    max_queue_size: int = Field(default=50, ge=5, le=200)
    allow_duplicates: bool = False
    require_approval: bool = True


class VenueConfigUpdate(BaseModel):
    """Schema para actualizar configuracion de un local."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    max_songs_per_device: int | None = Field(None, ge=1, le=20)
    max_queue_size: int | None = Field(None, ge=5, le=200)
    allow_duplicates: bool | None = None
    is_active: bool | None = None
    require_approval: bool | None = None


class VenueResponse(VenueBase):
    """Schema de respuesta para un Venue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    max_songs_per_device: int
    max_queue_size: int
    allow_duplicates: bool
    is_active: bool
    require_approval: bool
    qr_token: str
    created_at: datetime
    updated_at: datetime


class VenueWithStats(VenueResponse):
    """Venue más contadores para el panel del super admin."""

    pending_count: int = 0
    waiting_count: int = 0
    clients_count: int = 0


class SuperVenueUpdate(VenueConfigUpdate):
    """Actualización total desde el super admin: config + credenciales."""

    admin_username: str | None = Field(None, min_length=3, max_length=100)
    admin_password: str | None = Field(None, min_length=6, max_length=71)
