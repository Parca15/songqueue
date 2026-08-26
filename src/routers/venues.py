"""
Router para gestión de locales (Venues).
CRUD de locales, generación de QR, y configuración.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.models.venue import Venue
from src.schemas.venue import VenueCreate, VenueResponse, VenueConfigUpdate
from src.utils.security import get_password_hash
from src.utils.qr_generator import generate_venue_qr_url, qr_to_base64
from src.utils.auth import get_current_admin

router = APIRouter()


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    venue_data: VenueCreate,
    db: AsyncSession = Depends(get_db),
) -> Venue:
    """Crea un nuevo local con configuración inicial."""
    import re
    slug = re.sub(r"[^\w\s-]", "", venue_data.name).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)

    result = await db.execute(select(Venue).where(Venue.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un local con ese nombre (slug duplicado)",
        )

    venue = Venue(
        name=venue_data.name,
        slug=slug,
        description=venue_data.description,
        max_songs_per_device=venue_data.max_songs_per_device,
        max_queue_size=venue_data.max_queue_size,
        allow_duplicates=venue_data.allow_duplicates,
        admin_username=venue_data.admin_username,
        admin_password_hash=get_password_hash(venue_data.admin_password),
    )
    db.add(venue)
    await db.commit()
    await db.refresh(venue)
    return venue


@router.get("/{venue_id}", response_model=VenueResponse)
async def get_venue(venue_id: int, db: AsyncSession = Depends(get_db)) -> Venue:
    """Obtiene un local por su ID."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")
    return venue


@router.get("/slug/{slug}", response_model=VenueResponse)
async def get_venue_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> Venue:
    """Obtiene un local por su slug."""
    result = await db.execute(select(Venue).where(Venue.slug == slug))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")
    return venue


@router.patch("/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: int,
    updates: VenueConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> Venue:
    """Actualiza la configuración de un local (solo admin del local)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")

    # Solo el admin de este local puede modificarlo
    if current_admin.id != venue.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar este local",
        )

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(venue, field, value)

    await db.commit()
    await db.refresh(venue)
    return venue


@router.get("/{venue_id}/qr")
async def get_venue_qr(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Venue = Depends(get_current_admin),
) -> dict[str, Any]:
    """Genera el QR code de un local (solo admin)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")

    if current_admin.id != venue.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver el QR de este local",
        )

    base_url = "http://localhost:8000"
    join_url = generate_venue_qr_url(base_url, venue.qr_token)
    qr_base64 = qr_to_base64(join_url)

    return {
        "venue_id": venue_id,
        "join_url": join_url,
        "qr_base64": qr_base64,
    }
