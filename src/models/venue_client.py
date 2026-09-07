"""
Modelo VenueClient (Cliente registrado de un local).
Cada persona que escanea el QR registra un nombre único dentro del local.
Ese nombre aparece junto a las canciones que solicita en el panel del admin.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.database import Base


class VenueClient(Base):
    """Representa el nombre registrado de un cliente en un local."""

    __tablename__ = "venue_clients"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name = Column(String(30), nullable=False)
    device_fingerprint = Column(String(128), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Nombre único por local (mismo nombre en otro local sí está permitido)
    __table_args__ = (
        UniqueConstraint("venue_id", "display_name", name="uq_venue_client_name"),
    )

    # Relaciones
    venue = relationship("Venue", back_populates="clients")

    def __repr__(self) -> str:
        return f"<VenueClient(id={self.id}, venue_id={self.venue_id}, name='{self.display_name}')>"
