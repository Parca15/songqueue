"""
Schemas para el registro de nombres de clientes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientRegister(BaseModel):
    """Schema para registrar el nombre de un cliente en un local."""

    display_name: str = Field(..., min_length=1, max_length=30)
    device_fingerprint: str = Field(..., min_length=10, max_length=128)


class ClientResponse(BaseModel):
    """Schema de respuesta para un cliente registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    display_name: str
    created_at: datetime
