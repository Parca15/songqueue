"""
Schemas Pydantic para validación de datos de entrada y salida.
"""

from src.schemas.auth import AdminLogin, TokenResponse
from src.schemas.queue import (
    QueueItemCreate,
    QueueItemResponse,
    QueueReorder,
    QueueState,
)
from src.schemas.song import SongCreate, SongResponse, YouTubeSearchResult
from src.schemas.venue import VenueConfigUpdate, VenueCreate, VenueResponse

__all__ = [
    "VenueCreate",
    "VenueResponse",
    "VenueConfigUpdate",
    "SongCreate",
    "SongResponse",
    "YouTubeSearchResult",
    "QueueItemCreate",
    "QueueItemResponse",
    "QueueReorder",
    "QueueState",
    "AdminLogin",
    "TokenResponse",
]
