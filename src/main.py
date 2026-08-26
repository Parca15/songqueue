"""
Entry point de la aplicación FastAPI.
Configura middleware, eventos de lifecycle y monta los routers.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.database import init_db
from src.routers import venues, songs, queue, websocket

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la app."""
    # Startup
    if settings.debug:
        await init_db()
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    description="Sistema de cola de canciones multi-local con YouTube",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS — ajustar en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(venues.router, prefix="/api/v1/venues", tags=["venues"])
app.include_router(songs.router, prefix="/api/v1/songs", tags=["songs"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health", tags=["health"])
async def health_check():
    """Endpoint de health check para monitoreo."""
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}
