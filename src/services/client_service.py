"""
Servicio de registro de nombres de clientes.
Cada persona que escanea el QR registra un nombre único dentro del local.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.venue_client import VenueClient

MAX_NAME_LENGTH = 30


class NameTakenError(Exception):
    """El nombre ya está registrado por otro dispositivo en el local."""

    pass


async def register_client_name(
    db: AsyncSession,
    venue_id: int,
    display_name: str,
    device_fingerprint: str,
) -> VenueClient:
    """Registra (o re-confirma) el nombre de un cliente en un local.

    Comparación insensible a mayúsculas: "Carlos" y "carlos" son el mismo nombre.
    Idempotente: si el mismo dispositivo re-registra su nombre, no falla.
    """
    name = (display_name or "").strip()
    if not name:
        raise ValueError("El nombre no puede estar vacío")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"El nombre no puede superar {MAX_NAME_LENGTH} caracteres")

    result = await db.execute(
        select(VenueClient).where(
            VenueClient.venue_id == venue_id,
            func.lower(VenueClient.display_name) == name.lower(),
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.device_fingerprint == device_fingerprint:
            return existing  # Mismo dispositivo re-confirmando su nombre
        raise NameTakenError("Ese nombre ya está en uso, elige otro")

    client = VenueClient(
        venue_id=venue_id,
        display_name=name,
        device_fingerprint=device_fingerprint,
    )
    db.add(client)
    try:
        await db.commit()
    except IntegrityError:
        # Carrera concurrente: otro lo registró primero
        await db.rollback()
        raise NameTakenError("Ese nombre ya está en uso, elige otro")
    await db.refresh(client)
    return client


async def get_client_name(
    db: AsyncSession, venue_id: int, device_fingerprint: str
) -> str | None:
    """Retorna el nombre registrado de un dispositivo en un local, si existe."""
    result = await db.execute(
        select(VenueClient).where(
            VenueClient.venue_id == venue_id,
            VenueClient.device_fingerprint == device_fingerprint,
        )
    )
    client = result.scalar_one_or_none()
    return client.display_name if client else None
