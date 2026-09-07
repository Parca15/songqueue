"""
Schemas para autenticación.
"""
from pydantic import BaseModel, Field


class AdminLogin(BaseModel):
    """Datos para login de administrador."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class TokenResponse(BaseModel):
    """Respuesta con token JWT."""
    access_token: str
    token_type: str = "bearer"
    role: str = "venue"
    venue_id: int | None = None
    venue_name: str | None = None


class TokenPayload(BaseModel):
    """Payload decodificado del token."""
    sub: str | None = None
    role: str | None = None
    exp: int | None = None
