"""
Modelos Playlist y PlaylistItem.
Playlists creadas por el admin para reproducir en el local.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Playlist(Base):
    """Una playlist creada por el admin de un local."""

    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    venue = relationship("Venue", back_populates="playlists")
    items = relationship("PlaylistItem", back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.position")

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, name='{self.name}')>"


class PlaylistItem(Base):
    """Una cancion dentro de una playlist."""

    __tablename__ = "playlist_items"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False, index=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    playlist = relationship("Playlist", back_populates="items")
    song = relationship("Song")

    def __repr__(self) -> str:
        return f"<PlaylistItem(id={self.id}, playlist_id={self.playlist_id}, pos={self.position})>"
