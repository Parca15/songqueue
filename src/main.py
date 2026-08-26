"""
Entry point de la aplicación FastAPI.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.database import init_db
from src.routers import venues, songs, queue, websocket, auth

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Sistema de cola de canciones multi-local con YouTube",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "error": str(exc) if settings.debug else None},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ── Routers ──
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(venues.router, prefix="/api/v1/venues", tags=["venues"])
app.include_router(songs.router, prefix="/api/v1/songs", tags=["songs"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

# ── Static files (frontend) ──
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}


@app.get("/")
async def root():
    return {"message": "SongQueue API", "docs": "/docs", "version": "1.0.0"}
