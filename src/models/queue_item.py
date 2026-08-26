"""
Modelo QueueItem (Elemento de Cola).
Relaciona una canción con un local en una posición específica.
"""
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from src.database import Base


class QueueStatus(str, PyEnum):
    """Estados posibles de un item en la cola."""
    PENDING = "pending"
    PLAYING = "playing"
    PLAYED = "played"
    SKIPPED = "skipped"
    REMOVED = "removed"


class QueueItem(Base):
    """Representa una canción en la cola de un local."""

    __tablename__ = "queue_items"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    device_fingerprint = Column(String(128), nullable=False, index=True)

    # Orden en la cola (posición)
    position = Column(Integer, nullable=False, default=0)

    # Estado
    status = Column(Enum(QueueStatus), default=QueueStatus.PENDING, nullable=False)

    # Info del que solicitó
    requested_by = Column(String(100), nullable=True)  # Nickname opcional

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    played_at = Column(DateTime, nullable=True)

    # Relaciones
    venue = relationship("Venue", back_populates="queue_items")
    song = relationship("Song", back_populates="queue_items")

    def __repr__(self) -> str:
        return f"<QueueItem(id={self.id}, venue_id={self.venue_id}, pos={self.position}, status={self.status})>"
