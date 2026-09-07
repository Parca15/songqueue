"""
Servicio de usuarios globales (super admin).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.utils.security import get_password_hash

SUPERADMIN_ROLE = "superadmin"


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Busca un usuario global por nombre (comparación exacta)."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def ensure_superadmin(
    db: AsyncSession, username: str, password: str
) -> tuple[User, bool]:
    """Crea el super admin inicial si aún no existe. Retorna (usuario, creado).

    Idempotente: si ya hay un superadmin activo, no hace nada.
    """
    result = await db.execute(
        select(User).where(User.role == SUPERADMIN_ROLE, User.is_active.is_(True))
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    user = User(
        username=username.strip(),
        password_hash=get_password_hash(password),
        role=SUPERADMIN_ROLE,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, True
