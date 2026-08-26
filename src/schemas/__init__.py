"""
Schemas Pydantic para validación de datos de entrada y salida.
"""
from src.schemas.venue import VenueCreate, VenueResponse, VenueConfigUpdate
from src.schemas.song import SongCreate, SongResponse, YouTubeSearchResult
from src.schemas.queue import QueueItemCreate, QueueItemResponse, QueueReorder, QueueState
from src.schemas.auth import AdminLogin, TokenResponse

__all__ = [
    "VenueCreate", "VenueResponse", "VenueConfigUpdate",
    "SongCreate", "SongResponse", "YouTubeSearchResult",
    "QueueItemCreate", "QueueItemResponse", "QueueReorder", "QueueState",
    "AdminLogin", "TokenResponse",
]
