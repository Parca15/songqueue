"""
Entry point de la aplicacion FastAPI.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import AsyncSessionLocal, get_db, init_db
from src.routers import auth, playlist, queue, songs, superadmin, venues, websocket
from src.services.user_service import ensure_superadmin
from src.utils.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("songqueue")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion del ciclo de vida de la app."""
    # En modo debug, intentar crear tablas (no falla si BD no disponible)
    if settings.debug:
        try:
            await init_db()
            logger.info("Tablas verificadas/creadas")
        except Exception as e:
            logger.warning(f"init_db() omitido: {e}")
            logger.warning("Ejecuta: docker-compose up -d db")
    # Bootstrap del super admin (solo si está configurado y no existe ninguno)
    if settings.super_admin_username and settings.super_admin_password:
        try:
            async with AsyncSessionLocal() as session:
                _, created = await ensure_superadmin(
                    session,
                    settings.super_admin_username,
                    settings.super_admin_password,
                )
                if created:
                    logger.info(f"Super admin '{settings.super_admin_username}' creado")
        except Exception as e:
            logger.warning(f"ensure_superadmin() omitido: {e}")
    else:
        logger.info(
            "Sin SUPER_ADMIN_USERNAME/PASSWORD: login de super admin no disponible"
        )
    yield
    # Shutdown


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
    # Mismo origen por defecto (nginx/tunnel sirven web+api juntas).
    # Para deploys split, definir CORS_ORIGINS="https://app.ejemplo.com".
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "error": str(exc) if settings.debug else None,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas solicitudes, intenta de nuevo en un momento"},
    )


app.state.limiter = limiter


# ── Routers ──
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(superadmin.router, prefix="/api/v1/super", tags=["superadmin"])
app.include_router(venues.router, prefix="/api/v1/venues", tags=["venues"])
app.include_router(songs.router, prefix="/api/v1/songs", tags=["songs"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(playlist.router, prefix="/api/v1/playlists", tags=["playlists"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

# ── Frontend (archivos estáticos servidos por FastAPI) ──
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def _serve_frontend(filename: str):
    """Sirve un archivo del frontend. Retorna 404 si no existe."""
    filepath = FRONTEND_DIR / filename
    if filepath.is_file():
        return FileResponse(filepath)
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Sirve admin.html (raíz) o index.html (si ?venue= está presente)."""
    venue = request.query_params.get("venue")
    filename = "index.html" if venue else "admin.html"
    return _serve_frontend(filename)


@app.get("/admin.html", response_class=HTMLResponse)
async def admin_page():
    return _serve_frontend("admin.html")


@app.get("/index.html", response_class=HTMLResponse)
async def index_page():
    return _serve_frontend("index.html")


@app.get("/player.html", response_class=HTMLResponse)
async def player_page():
    return _serve_frontend("player.html")


@app.get("/join.html", response_class=HTMLResponse)
async def join_page():
    return _serve_frontend("join.html")


@app.get("/join/{token}", response_class=HTMLResponse)
async def join_token(token: str):
    """Ruta legacy: /join/<qr_token> sirve join.html."""
    return _serve_frontend("join.html")


@app.get("/design-system.css")
async def design_system_css():
    return _serve_frontend("design-system.css")


@app.get("/motion.js")
async def motion_js():
    return _serve_frontend("motion.js")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.version}


@app.get("/ready", tags=["health"])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness: verifica que la base de datos responde."""
    await db.execute(select(1))
    return {"status": "ready", "app": settings.app_name, "version": settings.version}


@app.get("/api", tags=["info"])
async def api_root():
    """Info de la API en JSON."""
    return {"message": "SongQueue API", "docs": "/docs", "version": settings.version}
