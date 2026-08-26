"""
Servicio de integración con YouTube Data API v3.
Busca videos y extrae metadata.
"""
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import get_settings
from src.schemas.song import YouTubeSearchResult

settings = get_settings()


def get_youtube_client() -> Any:
    """Crea un cliente de la API de YouTube."""
    if not settings.youtube_api_key:
        raise ValueError("YOUTUBE_API_KEY no está configurada")
    return build("youtube", "v3", developerKey=settings.youtube_api_key, cache_discovery=False)


async def search_youtube(query: str, max_results: int = 10) -> list[YouTubeSearchResult]:
    """Busca videos en YouTube por query."""
    try:
        youtube = get_youtube_client()
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=max_results,
            videoEmbeddable="true",
        )
        response = request.execute()

        results = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            results.append(YouTubeSearchResult(
                youtube_id=video_id,
                title=snippet["title"],
                channel=snippet["channelTitle"],
                thumbnail_url=snippet["thumbnails"]["medium"]["url"],
            ))
        return results
    except HttpError as e:
        raise RuntimeError(f"Error de YouTube API: {e}") from e


async def get_video_details(youtube_id: str) -> YouTubeSearchResult | None:
    """Obtiene detalles de un video específico."""
    try:
        youtube = get_youtube_client()
        request = youtube.videos().list(
            id=youtube_id,
            part="snippet,contentDetails",
        )
        response = request.execute()

        if not response["items"]:
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        duration = item["contentDetails"]["duration"]  # ISO 8601

        # Parsear duración ISO 8601 a segundos (simplificado)
        duration_seconds = _parse_iso_duration(duration)

        return YouTubeSearchResult(
            youtube_id=youtube_id,
            title=snippet["title"],
            channel=snippet["channelTitle"],
            thumbnail_url=snippet["thumbnails"]["medium"]["url"],
            duration_seconds=duration_seconds,
        )
    except HttpError:
        return None


def _parse_iso_duration(duration: str) -> int | None:
    """Parsea duración ISO 8601 (PT4M13S) a segundos."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds
