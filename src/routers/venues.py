"""
Router para gestion de locales (Venues).
CRUD de locales, generacion de QR, y configuracion.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.venue import Venue
from src.schemas.client import ClientRegister, ClientResponse
from src.schemas.venue import VenueConfigUpdate, VenueCreate, VenueResponse
from src.services.client_service import NameTakenError, register_client_name
from src.utils.auth import (
    Principal,
    SuperAdminPrincipal,
    get_current_principal,
    get_current_superadmin,
    require_venue_access,
)
from src.utils.qr_generator import qr_to_base64
from src.utils.rate_limit import limiter
from src.utils.security import get_password_hash

router = APIRouter()


@router.get("", response_model=list[VenueResponse])
async def list_venues(db: AsyncSession = Depends(get_db)) -> list[Venue]:
    """Lista todos los locales activos (sin exponer credenciales)."""
    result = await db.execute(select(Venue).where(Venue.is_active.is_(True)))
    return result.scalars().all()


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    venue_data: VenueCreate,
    db: AsyncSession = Depends(get_db),
    _admin: SuperAdminPrincipal = Depends(get_current_superadmin),
) -> Venue:
    """Crea un nuevo local con configuracion inicial (solo super admin)."""
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
        require_approval=venue_data.require_approval,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )
    return venue


@router.get("/slug/{slug}", response_model=VenueResponse)
async def get_venue_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> Venue:
    """Obtiene un local por su slug."""
    result = await db.execute(select(Venue).where(Venue.slug == slug))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )
    return venue


@router.get("/token/{qr_token}", response_model=VenueResponse)
async def get_venue_by_qr_token(
    qr_token: str, db: AsyncSession = Depends(get_db)
) -> Venue:
    """Obtiene un local publicamente por su QR token (sin auth)."""
    result = await db.execute(
        select(Venue).where(Venue.qr_token == qr_token, Venue.is_active.is_(True))
    )
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )
    return venue


@router.patch("/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: int,
    updates: VenueConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> Venue:
    """Actualiza la configuracion de un local (admin del local o super admin)."""
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )

    require_venue_access(current_admin, venue.id)

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(venue, field, value)

    await db.commit()
    await db.refresh(venue)
    return venue


@router.post(
    "/{venue_id}/register-name",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def register_client(
    request: Request,
    venue_id: int,
    body: ClientRegister,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Registra el nombre de un cliente en un local (público, desde el QR).

    El nombre es único por local (insensible a mayúsculas). Si ya está en uso
    por otro dispositivo → 409. Idempotente para el mismo dispositivo.
    """
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue or not venue.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local no encontrado o inactivo",
        )

    try:
        client = await register_client_name(
            db, venue_id, body.display_name, body.device_fingerprint
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NameTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return client


@router.get("/{venue_id}/qr")
async def get_venue_qr(
    venue_id: int,
    request: Request,
    base_url: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_admin: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Genera el QR code de un local (admin del local o super admin).

    `base_url` permite indicar la URL base real (p.ej. la IP LAN del host) para
    que el QR funcione desde otros dispositivos en la misma red.
    """
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Local no encontrado"
        )

    require_venue_access(current_admin, venue.id)

    import os

    from src.config import get_settings
    from src.utils.qr_generator import get_server_base_url

    # Se recolectan candidatos y se elige el primero que NO sea localhost,
    # para que el QR apunte siempre a una direccion alcanzable desde el celular.
    # Orden: base_url del panel -> SERVER_BASE_URL (env) -> Host header -> .local/IP.
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    host = request.headers.get("host", "")
    candidates = []
    if base_url:
        candidates.append(base_url)
    env_base = get_settings().server_base_url or os.environ.get("SERVER_BASE_URL")
    if env_base:
        candidates.append(env_base)
    if host:
        candidates.append(f"{scheme}://{host}")

    def _is_local(c: str) -> bool:
        h = c.split("://", 1)[-1].split(":")[0]
        return h in ("localhost", "127.0.0.1")

    base_url = next((c for c in candidates if not _is_local(c)), None)
    if not base_url:
        base_url = get_server_base_url()
    join_url = f"{base_url}/join/{venue.qr_token}"
    qr_base64 = qr_to_base64(join_url)

    return {
        "venue_id": venue_id,
        "join_url": join_url,
        "qr_base64": qr_base64,
    }
