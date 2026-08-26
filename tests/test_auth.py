"""
Tests para autenticacion.
"""
import pytest


class TestAuth:
    """Suite de tests para autenticacion."""

    async def test_login_success(self, client):
        """Test: Login exitoso retorna token JWT."""
        # Crear venue primero
        await client.post("/api/v1/venues", json={
            "name": "Auth Test Bar",
            "admin_username": "admin_auth",
            "admin_password": "authpass123",
        })

        response = await client.post("/api/v1/auth/login", json={
            "username": "admin_auth",
            "password": "authpass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["venue_name"] == "Auth Test Bar"

    async def test_login_wrong_password(self, client):
        """Test: Login con password incorrecto."""
        await client.post("/api/v1/venues", json={
            "name": "Auth Fail Bar",
            "admin_username": "admin_fail",
            "admin_password": "correctpass",
        })

        response = await client.post("/api/v1/auth/login", json={
            "username": "admin_fail",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client):
        """Test: Login con usuario que no existe."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "somepass",
        })
        assert response.status_code == 401

    async def test_protected_endpoint_without_token(self, client):
        """Test: Endpoint protegido sin token retorna 401."""
        response = await client.patch("/api/v1/venues/1", json={"name": "Hacked"})
        assert response.status_code == 401

    async def test_protected_endpoint_with_invalid_token(self, client):
        """Test: Endpoint protegido con token invalido retorna 401."""
        response = await client.patch(
            "/api/v1/venues/1",
            json={"name": "Hacked"},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    async def test_admin_can_only_modify_own_venue(self, client):
        """Test: Admin solo puede modificar su propio local."""
        # Crear dos venues
        v1 = await client.post("/api/v1/venues", json={
            "name": "Venue One",
            "admin_username": "admin_one",
            "admin_password": "pass123",
        })
        v1_id = v1.json()["id"]

        v2 = await client.post("/api/v1/venues", json={
            "name": "Venue Two",
            "admin_username": "admin_two",
            "admin_password": "pass123",
        })
        v2_id = v2.json()["id"]

        # Login como admin_one
        login = await client.post("/api/v1/auth/login", json={
            "username": "admin_one",
            "password": "pass123",
        })
        token = login.json()["access_token"]

        # Intentar modificar venue_two con token de admin_one
        response = await client.patch(
            f"/api/v1/venues/{v2_id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
