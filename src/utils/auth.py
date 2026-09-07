"""
Dependencias de autenticación para FastAPI.
Protege endpoints de admin con JWT (por local o super admin global).
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.models.venue import Venue
from src.utils.security import decode_access_token

security = HTTPBearer(auto_error=False)

ROLE_VENUE = "venue"
ROLE_SUPERADMIN = "superadmin"


@dataclass
class SuperAdminPrincipal:
    """Principal en memoria para el super admin (no es un Venue)."""

    id: int = 0
    username: str = ""
    role: str = ROLE_SUPERADMIN

    @property
    def name(self) -> str:
        return self.username


# Quien puede autenticarse: un local o el super admin.
Principal = Venue | SuperAdminPrincipal


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Verifica el JWT y retorna el principal: Venue o SuperAdminPrincipal.

    Tokens viejos sin claim `role` se tratan como venue (compatibilidad).
    """
    if not credentials:
        raise _unauthorized("Token de autenticación requerido")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _unauthorized("Token inválido o expirado")

    sub = payload.get("sub")
    if not sub:
        raise _unauthorized("Token malformado")

    role = payload.get("role", ROLE_VENUE)

    if role == ROLE_SUPERADMIN:
        result = await db.execute(select(User).where(User.id == int(sub)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active or user.role != ROLE_SUPERADMIN:
            raise _unauthorized("Super admin no encontrado o inactivo")
        return SuperAdminPrincipal(id=user.id, username=user.username)

    result = await db.execute(select(Venue).where(Venue.id == int(sub)))
    venue = result.scalar_one_or_none()

    if not venue or not venue.is_active:
        raise _unauthorized("Local no encontrado o inactivo")

    return venue


async def get_current_admin(
    principal: Principal = Depends(get_current_principal),
) -> Venue:
    """Dependency clásica: solo el admin de un local (rechaza al super admin).

    Se mantiene para endpoints que son exclusivos del tenant.
    """
    if isinstance(principal, SuperAdminPrincipal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint es solo para admins de local",
        )
    return principal


async def get_current_superadmin(
    principal: Principal = Depends(get_current_principal),
) -> SuperAdminPrincipal:
    """Dependency exclusiva del super admin."""
    if not isinstance(principal, SuperAdminPrincipal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere super admin",
        )
    return principal


def require_venue_access(principal: Principal, venue_id: int) -> None:
    """Permite si es super admin o el admin del local indicado. Si no, 403."""
    if isinstance(principal, SuperAdminPrincipal):
        return
    if principal.id != venue_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para este local",
        )
