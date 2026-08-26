"""
Router de autenticación para administradores de locales.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.models.venue import Venue
from src.schemas.auth import AdminLogin, TokenResponse
from src.utils.security import verify_password, create_access_token

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def admin_login(
    credentials: AdminLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Login de administrador de un local.
    Retorna un JWT token para usar en endpoints protegidos.
    """
    result = await db.execute(
        select(Venue).where(Venue.admin_username == credentials.username)
    )
    venue = result.scalar_one_or_none()

    if not venue or not venue.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not verify_password(credentials.password, venue.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    access_token = create_access_token(data={"sub": str(venue.id)})

    return TokenResponse(
        access_token=access_token,
        venue_id=venue.id,
        venue_name=venue.name,
    )
