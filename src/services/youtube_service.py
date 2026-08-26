"""
Servicio de integracion con YouTube.
Orden de busqueda: YouTube API -> yt-dlp (local) -> Piped -> Invidious
"""
import asyncio
import time
from typing import Any

import httpx

from src.config import get_settings
from src.schemas.song import YouTubeSearchResult

settings = get_settings()

# ── Instancias Piped (gratis, sin API key) ──
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi-libre.kavin.rocks",
    "https://pipedapi.drgns.space",
    "https://pipedapi.ggtyler.dev",
    "https://pipedapi.owo.si",
    "https://pipedapi.nosebs.ru",
    "https://api.piped.minionflo.net",
]

# ── Instancias Invidious (gratis, sin API key) ──
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.f5.si",
]

# ── Genre detection ──

GENRE_KEYWORDS = {
    "reggaeton": ["reggaeton", "reggaetón", "daddy yankee", "j balvin", "ozuna", "bad bunny", "nicky jam", "karol g", "luny tunes"],
    "salsa": ["salsa", "celia cruz", "héctor lavoe", "marco antonio solís"],
    "cumbia": ["cumbia", "sonora dinamita", "los ángeles azules", "grupo niche"],
    "bachata": ["bachata", "romeo santos", "anthony santos", "aventura"],
    "merengue": ["merengue", "merengue urbano"],
    "pop": ["pop", "taylor swift", "ariana grande", "dua lipa", "ed sheeran", "shakira"],
    "rock": ["rock", "green day", "nirvana", "queen", "led zeppelin", "ac/dc"],
    "hip hop": ["hip hop", "rap", "drake", "kendrick", "travis scott"],
    "electronic": ["electronic", "edm", "david guetta", "calvin harris", "marshmello", "diplo"],
    "latin": ["latin", "latin pop"],
    "country": ["country", "luke bryan", "blake shelton"],
    "r&b": ["r&b", "rnb", "soul", "rhythm and blues"],
    "jazz": ["jazz", "miles davis", "john coltrane"],
    "classical": ["classical", "orchestra", "symphony", "mozart", "beethoven"],
    "kpop": ["kpop", "k-pop", "bts", "blackpink", "twice", "stray kids"],
}


def detect_genre(title: str, channel: str) -> str | None:
    """Detecta género musical basado en título y canal."""
    text = f"{title} {channel}".lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return genre
    return None


# ── Caché simple con TTL ──
_cache: dict[str, tuple[float, list[YouTubeSearchResult]]] = {}
CACHE_TTL = 300  # 5 minutos


def _get_cache_key(query: str, max_results: int) -> str:
    return f"{query}:{max_results}"


def _check_cache(query: str, max_results: int) -> list[YouTubeSearchResult] | None:
    key = _get_cache_key(query, max_results)
    if key in _cache:
        ts, results = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return results
        del _cache[key]
    return None


def _set_cache(query: str, max_results: int, results: list[YouTubeSearchResult]) -> None:
    key = _get_cache_key(query, max_results)
    _cache[key] = (time.time(), results)


# ── YouTube Client (lazy singleton) ──
_youtube_client: Any = None


def _get_youtube_client() -> Any:
    global _youtube_client
    if _youtube_client is None:
        if not settings.youtube_api_key:
            raise ValueError("YOUTUBE_API_KEY no esta configurada")
        from googleapiclient.discovery import build
        _youtube_client = build(
            "youtube", "v3",
            developerKey=settings.youtube_api_key,
            cache_discovery=False,
        )
    return _youtube_client


async def search_youtube(query: str, max_results: int = 10) -> list[YouTubeSearchResult]:
    """Busca videos. Orden: cache -> yt-dlp -> YouTube API -> Piped -> Invidious."""
    # 1. Verificar cache
    cached = _check_cache(query, max_results)
    if cached is not None:
        return cached

    # 2. Intentar yt-dlp (rapido, confiable, sin API key)
    try:
        results = await _search_ytdlp(query, max_results)
        if results:
            _set_cache(query, max_results, results)
            return results
    except Exception as e:
        print(f"yt-dlp fallo: {e}")

    # 3. Intentar YouTube Data API (lento si la key no funciona)
    if settings.youtube_api_key:
        try:
            results = await _search_youtube_api(query, max_results)
            if results:
                _set_cache(query, max_results, results)
                return results
        except Exception as e:
            print(f"YouTube API fallo: {e}")

    # 4. Fallback a Piped
    try:
        results = await _search_piped(query, max_results)
        if results:
            _set_cache(query, max_results, results)
            return results
    except Exception as e:
        print(f"Piped fallo: {e}")

    # 5. Fallback a Invidious
    results = await _search_invidious(query, max_results)
    if results:
        _set_cache(query, max_results, results)
    return results


async def get_video_details(youtube_id: str) -> YouTubeSearchResult | None:
    """Obtiene detalles de un video."""
    if settings.youtube_api_key:
        try:
            return await _get_video_details_api(youtube_id)
        except Exception as e:
            print(f"YouTube API fallo para detalles: {e}")

    try:
        return await _get_video_details_ytdlp(youtube_id)
    except Exception:
        pass

    try:
        return await _get_video_details_piped(youtube_id)
    except Exception:
        pass

    return await _get_video_details_invidious(youtube_id)


# ── YouTube Data API v3 ──

async def _search_youtube_api(query: str, max_results: int) -> list[YouTubeSearchResult]:
    youtube = _get_youtube_client()
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results,
        videoEmbeddable="true",
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, request.execute)

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


async def _get_video_details_api(youtube_id: str) -> YouTubeSearchResult | None:
    youtube = _get_youtube_client()
    request = youtube.videos().list(
        id=youtube_id,
        part="snippet,contentDetails",
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, request.execute)

    if not response["items"]:
        return None

    item = response["items"][0]
    snippet = item["snippet"]
    duration = item["contentDetails"]["duration"]

    return YouTubeSearchResult(
        youtube_id=youtube_id,
        title=snippet["title"],
        channel=snippet["channelTitle"],
        thumbnail_url=snippet["thumbnails"]["medium"]["url"],
        duration_seconds=_parse_iso_duration(duration),
    )


# ── yt-dlp (busqueda local, sin API key) ──

# ── Filtro de videos reproducibles ──

async def _filter_embeddable(videos: list[YouTubeSearchResult]) -> list[YouTubeSearchResult]:
    """Filtra videos que no se pueden reproducir (bloqueados por copyright, etc)."""
    async def check_embeddable(video: YouTubeSearchResult) -> YouTubeSearchResult | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video.youtube_id}&format=json"
                resp = await client.get(url)
                if resp.status_code == 200:
                    return video
        except Exception:
            pass
        return None

    tasks = [check_embeddable(v) for v in videos]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def is_video_embeddable(youtube_id: str) -> bool:
    """Verifica si un video de YouTube se puede incrustar (no bloqueado por copyright)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={youtube_id}&format=json"
            resp = await client.get(url)
            return resp.status_code == 200
    except Exception:
        return True  # Si no se puede verificar, permitir por defecto


async def _search_ytdlp(query: str, max_results: int) -> list[YouTubeSearchResult]:
    """Busca videos usando yt-dlp (extrae info de YouTube sin API key)."""
    import yt_dlp

    def _extract():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results + 5}:{query}", download=False)
            return result.get("entries", []) if result else []

    loop = asyncio.get_event_loop()
    entries = await loop.run_in_executor(None, _extract)

    results = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id", "")
        title = entry.get("title", "Sin titulo")
        channel = entry.get("uploader", entry.get("channel", "Unknown"))
        results.append(YouTubeSearchResult(
            youtube_id=video_id,
            title=title,
            channel=channel,
            thumbnail_url=entry.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"),
            duration_seconds=entry.get("duration"),
            genre=detect_genre(title, channel),
        ))

    if not results:
        return results

    print(f"yt-dlp retorno {len(results)} resultados")
    return results[:max_results]


async def _get_video_details_ytdlp(youtube_id: str) -> YouTubeSearchResult | None:
    """Obtiene detalles de video usando yt-dlp."""
    import yt_dlp

    def _extract():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=False)

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _extract)

    if not info:
        return None

    return YouTubeSearchResult(
        youtube_id=youtube_id,
        title=info.get("title", "Sin titulo"),
        channel=info.get("uploader", info.get("channel", "Unknown")),
        thumbnail_url=info.get("thumbnail", f"https://i.ytimg.com/vi/{youtube_id}/mqdefault.jpg"),
        duration_seconds=info.get("duration"),
    )


# ── Stream URL extraction ──

async def get_stream_url(youtube_id: str) -> str | None:
    """Obtiene la URL directa del stream de video usando yt-dlp."""
    import yt_dlp

    def _extract():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=False)
            return info

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _extract)
        if info:
            url = info.get("url")
            if url:
                return url
            formats = info.get("formats", [])
            for fmt in reversed(formats):
                if fmt.get("ext") == "mp4" and fmt.get("url"):
                    return fmt["url"]
            if formats:
                return formats[-1].get("url")
    except Exception as e:
        print(f"Error getting stream URL for {youtube_id}: {e}")
    return None


# ── Piped API (gratis, sin API key) ──

async def _search_piped(query: str, max_results: int) -> list[YouTubeSearchResult]:
    """Busca videos usando Piped API."""
    for instance in PIPED_INSTANCES:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"{instance}/streams"
                params = {"search": query}
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if not isinstance(data, dict) or "items" not in data:
                    continue

                results = []
                for item in data["items"]:
                    if item.get("type") != "stream":
                        continue
                    results.append(YouTubeSearchResult(
                        youtube_id=item["url"],
                        title=item.get("title", "Sin titulo"),
                        channel=item.get("uploaderName", "Unknown"),
                        thumbnail_url=item.get("thumbnailUrl", ""),
                        duration_seconds=item.get("duration"),
                    ))
                    if len(results) >= max_results:
                        break

                if results:
                    print(f"Piped ({instance}) retorno {len(results)} resultados")
                    return results
        except Exception as e:
            print(f"Piped {instance} fallo: {e}")
            continue

    return []


async def _get_video_details_piped(youtube_id: str) -> YouTubeSearchResult | None:
    """Obtiene detalles de video usando Piped API."""
    for instance in PIPED_INSTANCES:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"{instance}/streams/{youtube_id}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                return YouTubeSearchResult(
                    youtube_id=youtube_id,
                    title=data.get("title", "Sin titulo"),
                    channel=data.get("uploader", "Unknown"),
                    thumbnail_url=data.get("thumbnailUrl", ""),
                    duration_seconds=data.get("duration"),
                )
        except Exception as e:
            print(f"Piped {instance} fallo para video {youtube_id}: {e}")
            continue

    return None


# ── Invidious API (gratis, sin API key) ──

async def _search_invidious(query: str, max_results: int) -> list[YouTubeSearchResult]:
    """Busca videos usando Invidious API."""
    for instance in INVIDIOUS_INSTANCES:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"{instance}/api/v1/search"
                params = {
                    "q": query,
                    "type": "video",
                    "sort_by": "relevance",
                    "page": 1,
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if not isinstance(data, list):
                    print(f"Invidious {instance} retorno formato inesperado: {type(data)}")
                    continue

                results = []
                for item in data:
                    if item.get("type") != "video":
                        continue
                    results.append(YouTubeSearchResult(
                        youtube_id=item["videoId"],
                        title=item["title"],
                        channel=item.get("author", "Unknown"),
                        thumbnail_url=_get_best_thumbnail(item.get("videoThumbnails", [])),
                        duration_seconds=item.get("lengthSeconds"),
                    ))
                    if len(results) >= max_results:
                        break

                if results:
                    print(f"Invidious ({instance}) retorno {len(results)} resultados")
                    return results
        except Exception as e:
            print(f"Invidious {instance} fallo: {e}")
            continue

    print("Ninguna fuente de busqueda disponible")
    return []


async def _get_video_details_invidious(youtube_id: str) -> YouTubeSearchResult | None:
    """Obtiene detalles de video usando Invidious API."""
    for instance in INVIDIOUS_INSTANCES:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"{instance}/api/v1/videos/{youtube_id}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                return YouTubeSearchResult(
                    youtube_id=youtube_id,
                    title=data["title"],
                    channel=data.get("author", "Unknown"),
                    thumbnail_url=_get_best_thumbnail(data.get("videoThumbnails", [])),
                    duration_seconds=data.get("lengthSeconds"),
                )
        except Exception as e:
            print(f"Invidious {instance} fallo para video {youtube_id}: {e}")
            continue

    return None


def _get_best_thumbnail(thumbnails: list[dict]) -> str:
    """Obtiene la mejor thumbnail disponible."""
    if not thumbnails:
        return ""
    for t in thumbnails:
        if t.get("quality") == "medium":
            return t["url"]
    return thumbnails[0].get("url", "")


def _parse_iso_duration(duration: str) -> int | None:
    """Parsea duracion ISO 8601 (PT4M13S) a segundos."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds
