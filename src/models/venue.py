"""
Modelo Venue (Local/Establecimiento).
Cada local tiene su propia cola, QR único y configuración.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from src.database import Base


class Venue(Base):
    """Representa un local donde se reproduce música."""

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Configuración de la cola
    max_songs_per_device = Column(Integer, default=3, nullable=False)
    max_queue_size = Column(Integer, default=50, nullable=False)
    allow_duplicates = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # QR y acceso
    qr_token = Column(String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)

    # Admin credentials (hashed)
    admin_username = Column(String(100), nullable=False)
    admin_password_hash = Column(String(255), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    queue_items = relationship("QueueItem", back_populates="venue", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="venue", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name='{self.name}', slug='{self.slug}')>"
