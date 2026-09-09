"""
Configuracion de SQLAlchemy para operaciones asincronas con MySQL.
Usa aiomysql como driver async.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from src.config import get_settings

settings = get_settings()

# TiDB Cloud Serverless requiere SSL; detectar por hostname en la URL.
_connect_args: dict = {}
if "tidbcloud.com" in settings.database_url:
    _connect_args = {"ssl": True}

# Motor async con pool de conexiones
# NOTA: pool_pre_ping desactivado por incompatibilidad con aiomysql 0.2.0
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    connect_args=_connect_args,
)

# Factory de sesiones async
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Base declarativa para modelos
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency de FastAPI para inyeccion de sesiones de BD."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Crea todas las tablas (util para desarrollo, en prod usar alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
