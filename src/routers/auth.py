"""
Router de autenticacion para administradores de locales.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.models.venue import Venue
from src.schemas.auth import AdminLogin, TokenResponse
from src.utils.auth import (
    ROLE_SUPERADMIN,
    ROLE_VENUE,
    Principal,
    SuperAdminPrincipal,
    get_current_principal,
)
from src.utils.rate_limit import limiter
from src.utils.security import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("30/minute")
async def admin_login(
    request: Request,
    credentials: AdminLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Login de super admin o de administrador de un local.
    Retorna un JWT token para usar en endpoints protegidos.
    """
    # 1. Intentar como super admin (usuarios globales)
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()
    if user and user.is_active and user.role == ROLE_SUPERADMIN:
        if verify_password(credentials.password, user.password_hash):
            access_token = create_access_token(
                data={"sub": str(user.id), "role": ROLE_SUPERADMIN}
            )
            return TokenResponse(
                access_token=access_token,
                role=ROLE_SUPERADMIN,
                venue_id=None,
                venue_name=None,
            )

    # 2. Intentar como admin de local
    result = await db.execute(
        select(Venue).where(Venue.admin_username == credentials.username)
    )
    venue = result.scalar_one_or_none()

    if not venue or not venue.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contrasena incorrectos",
        )

    if not verify_password(credentials.password, venue.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contrasena incorrectos",
        )

    access_token = create_access_token(data={"sub": str(venue.id), "role": ROLE_VENUE})

    return TokenResponse(
        access_token=access_token,
        role=ROLE_VENUE,
        venue_id=venue.id,
        venue_name=venue.name,
    )


@router.post("/logout")
async def admin_logout(
    principal: Principal = Depends(get_current_principal),
):
    """
    Logout de administrador.
    El cliente debe eliminar el token del localStorage.
    """
    if isinstance(principal, SuperAdminPrincipal):
        return {
            "message": "Logout exitoso",
            "venue_id": None,
            "venue_name": principal.username,
        }
    return {
        "message": "Logout exitoso",
        "venue_id": principal.id,
        "venue_name": principal.name,
    }
