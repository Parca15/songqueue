"""
Configuración de pytest para tests asíncronos.
Usa SQLite en archivo temporal (la memoria + NullPool pierde las tablas
entre conexiones).
"""
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.main import app
from src.database import Base, get_db
from src.config import Settings

# Base de datos temporal en archivo para tests
_fd, TEST_DB_PATH = tempfile.mkstemp(prefix="songqueue_test_", suffix=".db")
os.close(_fd)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    """Override del dependency get_db para tests."""
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Crea las tablas antes de todos los tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest_asyncio.fixture
async def super_headers(client):
    """Headers con token de super admin (crea el super si no existe)."""
    from src.services.user_service import ensure_superadmin

    async with TestingSessionLocal() as session:
        await ensure_superadmin(session, "test_super", "superpass123")
    resp = await client.post("/api/v1/auth/login", json={
        "username": "test_super",
        "password": "superpass123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def db_session():
    """Proporciona una sesión de BD limpia para cada test."""
    async with TestingSessionLocal() as session:
        yield session
        # Rollback después de cada test
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    """Cliente HTTP async para tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
