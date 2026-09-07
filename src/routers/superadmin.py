"""
Router del super admin: gestión total de cuentas (locales).
Solo accesible con token de super admin.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db
from src.models.queue_item import QueueItem, QueueStatus
from src.models.venue import Venue
from src.models.venue_client import VenueClient
from src.schemas.venue import VenueCreate, VenueResponse, VenueWithStats, SuperVenueUpdate
from src.utils.security import get_password_hash
from src.utils.auth import get_current_superadmin, SuperAdminPrincipal

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "-", slug)


async def _venue_with_stats(db: AsyncSession, venue: Venue) -> dict:
    pending = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue.id,
            QueueItem.status == QueueStatus.PENDING,
        )
    )
    waiting = await db.execute(
        select(func.count(QueueItem.id)).where(
            QueueItem.venue_id == venue.id,
            QueueItem.status == QueueStatus.WAITING,
        )
    )
    clients = await db.execute(
        select(func.count(VenueClient.id)).where(VenueClient.venue_id == venue.id)
    )
    data = VenueResponse.model_validate(venue).model_dump()
    data.update(
        pending_count=pending.scalar() or 0,
        waiting_count=waiting.scalar() or 0,
        clients_count=clients.scalar() or 0,
    )
    return data


@router.get("/venues", response_model=list[VenueWithStats])
async def list_all_venues(
    db: AsyncSession = Depends(get_db),
    _admin: SuperAdminPrincipal = Depends(get_current_superadmin),
) -> list[dict]:
    """Lista todas las cuentas (activas e inactivas) con estadísticas."""
    result = await db.execute(select(Venue).order_by(Venue.name))
    venues = result.scalars().all()
    return [await _venue_with_stats(db, v) for v in venues]


@router.post("/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue_as_super(
    venue_data: VenueCreate,
    db: AsyncSession = Depends(get_db),
    _admin: SuperAdminPrincipal = Depends(get_current_superadmin),
) -> Venue:
    """Crea una cuenta (local) nueva."""
    slug = _slugify(venue_data.name)

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
        require_approval=venue_data.require_approval,
        admin_username=venue_data.admin_username,
        admin_password_hash=get_password_hash(venue_data.admin_password),
    )
    db.add(venue)
    await db.commit()
    await db.refresh(venue)
    return venue


@router.patch("/venues/{venue_id}", response_model=VenueResponse)
async def update_venue_as_super(
    venue_id: int,
    updates: SuperVenueUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: SuperAdminPrincipal = Depends(get_current_superadmin),
) -> Venue:
    """Modifica una cuenta: nombre del local, credenciales, límites o estado."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")

    update_data = updates.model_dump(exclude_unset=True)

    new_password = update_data.pop("admin_password", None)
    if new_password is not None:
        venue.admin_password_hash = get_password_hash(new_password)

    for field, value in update_data.items():
        if field == "name" and value:
            new_slug = _slugify(value)
            clash = await db.execute(
                select(Venue).where(Venue.slug == new_slug, Venue.id != venue_id)
            )
            if clash.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe otro local con ese nombre",
                )
            venue.slug = new_slug
        setattr(venue, field, value)

    await db.commit()
    await db.refresh(venue)
    return venue


@router.delete("/venues/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venue_as_super(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: SuperAdminPrincipal = Depends(get_current_superadmin),
) -> None:
    """Borra una cuenta y todo lo asociado (cola, dispositivos, playlists, clientes)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado")

    await db.delete(venue)
    await db.commit()
