"""
Tests para el router de Venues.
"""
import uuid

import pytest


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


class TestVenues:
    """Suite de tests para gestion de locales."""

    async def _create_venue_and_login(self, client, super_headers):
        """Helper: Crea venue (como super) y hace login."""
        username = _uniq("admin_test")
        create_resp = await client.post("/api/v1/venues", json={
            "name": _uniq("Test Venue"),
            "admin_username": username,
            "admin_password": "testpass123",
            "max_songs_per_device": 3,
            "max_queue_size": 20,
        }, headers=super_headers)
        venue_id = create_resp.json()["id"]
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "testpass123",
        })
        token = login_resp.json()["access_token"]
        return venue_id, token

    async def test_create_venue(self, client, super_headers):
        response = await client.post("/api/v1/venues", json={
            "name": "Test Bar",
            "description": "Un bar de prueba",
            "admin_username": "admin_test",
            "admin_password": "testpass123",
            "max_songs_per_device": 3,
            "max_queue_size": 20,
            "allow_duplicates": False,
        }, headers=super_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Bar"
        assert data["slug"] == "test-bar"
        assert "qr_token" in data

    async def test_create_venue_requires_superadmin(self, client):
        response = await client.post("/api/v1/venues", json={
            "name": "Sneaky Bar",
            "admin_username": "sneaky",
            "admin_password": "pass123",
        })
        assert response.status_code in (401, 403)

    async def test_create_venue_duplicate_slug(self, client, super_headers):
        await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin1",
            "admin_password": "pass123",
        }, headers=super_headers)
        response = await client.post("/api/v1/venues", json={
            "name": "Duplicate Bar",
            "admin_username": "admin2",
            "admin_password": "pass123",
        }, headers=super_headers)
        assert response.status_code == 409

    async def test_get_venue(self, client, super_headers):
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Get Venue Test",
            "admin_username": "admin_get",
            "admin_password": "pass123",
        }, headers=super_headers)
        venue_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/venues/{venue_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Venue Test"

    async def test_get_venue_not_found(self, client):
        response = await client.get("/api/v1/venues/99999")
        assert response.status_code == 404

    async def test_update_venue_requires_auth(self, client, super_headers):
        create_resp = await client.post("/api/v1/venues", json={
            "name": "Protected Venue",
            "admin_username": "admin_prot",
            "admin_password": "pass123",
        }, headers=super_headers)
        venue_id = create_resp.json()["id"]
        # Sin token
        response = await client.patch(f"/api/v1/venues/{venue_id}", json={"name": "Hacked"})
        assert response.status_code == 401

    async def test_update_venue_with_auth(self, client, super_headers):
        venue_id, token = await self._create_venue_and_login(client, super_headers)
        response = await client.patch(
            f"/api/v1/venues/{venue_id}",
            json={"max_songs_per_device": 10, "allow_duplicates": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["max_songs_per_device"] == 10
        assert data["allow_duplicates"] is True

    async def test_get_venue_qr_requires_auth(self, client, super_headers):
        venue_id, token = await self._create_venue_and_login(client, super_headers)
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
