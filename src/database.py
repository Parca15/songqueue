"""
Configuracion de SQLAlchemy para operaciones asincronas con MySQL.
Usa aiomysql como driver async.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.config import get_settings

settings = get_settings()

# Motor async con pool de conexiones
# NOTA: pool_pre_ping desactivado por incompatibilidad con aiomysql 0.2.0
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
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
