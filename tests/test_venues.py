"""
Tests para el router de Venues.
"""
import pytest


class TestVenues:
    """Suite de tests para gestión de locales."""

    async def test_create_venue(self, client):
        """Test: Crear un nuevo local."""
        response = await client.post("/api/v1/venues", json={
            "name": "Test Bar",
            "description": "Un bar de prueba",
            "admin_username": "admin_test",
            "admin_password": "testpass123",
            "max_songs_per_device": 3,
            "max_queue_size": 20,
            "allow_duplicates": False,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Bar"
        assert data["slug"] == "test-bar"
        assert data["max_songs_per_device"] == 3
        assert "qr_token" in data
        assert "admin_password_hash" not in data  # No exponer hash

    async def test_create_venue_duplicate_slug(self, client):
        """Test: No permitir slug duplicado."""
        # Crear primero
        await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin1",
            "admin_password": "pass123",
        })
        # Intentar duplicar
        response = await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin2",
            "admin_password": "pass123",
        })
        assert response.status_code == 409

    async def test_get_venue(self, client):
        """Test: Obtener un local por ID."""
        # Crear
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Get Venue Test",
            "admin_username": "admin_get",
            "admin_password": "pass123",
        })
        venue_id = create_resp.json()["id"]

        # Obtener
        response = await client.get(f"/api/v1/venues/{venue_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == venue_id
        assert data["name"] == "Get Venue Test"

    async def test_get_venue_not_found(self, client):
        """Test: Local no encontrado."""
        response = await client.get("/api/v1/venues/99999")
        assert response.status_code == 404

    async def test_get_venue_by_slug(self, client):
        """Test: Obtener local por slug."""
        await client.post("/api/v1/venues", json={
            "name": "Slug Test",
            "admin_username": "admin_slug",
            "admin_password": "pass123",
        })
        response = await client.get("/api/v1/venues/slug/slug-test")
        assert response.status_code == 200
        assert response.json()["slug"] == "slug-test"

    async def test_update_venue(self, client):
        """Test: Actualizar configuración de un local."""
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Update Test",
            "admin_username": "admin_up",
            "admin_password": "pass123",
        })
        venue_id = create_resp.json()["id"]

        response = await client.patch(f"/api/v1/venues/{venue_id}", json={
            "max_songs_per_device": 10,
            "allow_duplicates": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["max_songs_per_device"] == 10
        assert data["allow_duplicates"] is True

    async def test_get_venue_qr(self, client):
        """Test: Generar QR de un local."""
        create_resp = await client.post("/api/v1/venues", json={
            "name": "QR Test",
            "admin_username": "admin_qr",
            "admin_password": "pass123",
        })
        venue_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/venues/{venue_id}/qr")
        assert response.status_code == 200
        data = response.json()
        assert "join_url" in data
        assert "qr_base64" in data
        assert data["qr_base64"].startswith("data:image/png;base64,")
