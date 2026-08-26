"""
Modelo Song (Canción).
Almacena metadata de videos de YouTube para evitar llamadas repetidas a la API.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from src.database import Base


class Song(Base):
    """Representa una canción/video de YouTube."""

    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    youtube_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    channel = Column(String(255), nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Duración en segundos

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    queue_items = relationship("QueueItem", back_populates="song")

    def __repr__(self) -> str:
        return f"<Song(id={self.id}, youtube_id='{self.youtube_id}', title='{self.title[:30]}...')>"
