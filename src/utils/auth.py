"""
Dependencias de autenticación para FastAPI.
Protege endpoints de admin con JWT.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.models.venue import Venue
from src.utils.security import decode_access_token

security = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Venue:
    """
    Dependency que verifica el token JWT y retorna el Venue (admin) autenticado.
    Usar en endpoints que requieren permisos de administrador.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    venue_id = payload.get("sub")
    if not venue_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado",
        )

    result = await db.execute(select(Venue).where(Venue.id == int(venue_id)))
    venue = result.scalar_one_or_none()

    if not venue or not venue.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Local no encontrado o inactivo",
        )

    return venue


async def get_optional_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Venue | None:
    """
    Dependency opcional: retorna el admin si hay token válido, None si no.
    Útil para endpoints que funcionan para usuarios y admins.
    """
    if not credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    venue_id = payload.get("sub")
    if not venue_id:
        return None

    result = await db.execute(select(Venue).where(Venue.id == int(venue_id)))
    return result.scalar_one_or_none()
