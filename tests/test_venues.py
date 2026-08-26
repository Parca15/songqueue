"""
Tests para el router de Venues.
"""
import pytest


class TestVenues:
    """Suite de tests para gestion de locales."""

    async def _create_venue_and_login(self, client):
        """Helper: Crea venue y hace login."""
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Test Venue",
            "admin_username": "admin_test",
            "admin_password": "testpass123",
            "max_songs_per_device": 3,
            "max_queue_size": 20,
        })
        venue_id = create_resp.json()["id"]
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "admin_test",
            "password": "testpass123",
        })
        token = login_resp.json()["access_token"]
        return venue_id, token

    async def test_create_venue(self, client):
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
        assert "qr_token" in data

    async def test_create_venue_duplicate_slug(self, client):
        await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin1",
            "admin_password": "pass123",
        })
        response = await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin2",
            "admin_password": "pass123",
        })
        assert response.status_code == 409

    async def test_get_venue(self, client):
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Get Venue Test",
            "admin_username": "admin_get",
            "admin_password": "pass123",
        })
        venue_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/venues/{venue_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Venue Test"

    async def test_get_venue_not_found(self, client):
        response = await client.get("/api/v1/venues/99999")
        assert response.status_code == 404

    async def test_update_venue_requires_auth(self, client):
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Protected Venue",
            "admin_username": "admin_prot",
            "admin_password": "pass123",
        })
        venue_id = create_resp.json()["id"]
        # Sin token
        response = await client.patch(f"/api/v1/venues/{venue_id}", json={"name": "Hacked"})
        assert response.status_code == 401

    async def test_update_venue_with_auth(self, client):
        venue_id, token = await self._create_venue_and_login(client)
        response = await client.patch(
            f"/api/v1/venues/{venue_id}",
            json={"max_songs_per_device": 10, "allow_duplicates": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["max_songs_per_device"] == 10
        assert data["allow_duplicates"] is True

    async def test_get_venue_qr_requires_auth(self, client):
        venue_id, token = await self._create_venue_and_login(client)
        # Sin token
        response = await client.get(f"/api/v1/venues/{venue_id}/qr")
        assert response.status_code == 401
        # Con token
        response = await client.get(
            f"/api/v1/venues/{venue_id}/qr",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "qr_base64" in data
        assert data["qr_base64"].startswith("data:image/png;base64,")
