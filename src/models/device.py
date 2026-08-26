"""
Modelo Device (Dispositivo).
Rastrea dispositivos por fingerprint para limitar canciones por dispositivo.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Device(Base):
    """Representa un dispositivo que ha interactuado con un local."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint = Column(String(128), nullable=False, index=True)

    # Contador de canciones activas en cola
    songs_in_queue = Column(Integer, default=0, nullable=False)

    # Metadata opcional
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    venue = relationship("Venue", back_populates="devices")

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, venue_id={self.venue_id}, songs={self.songs_in_queue})>"
