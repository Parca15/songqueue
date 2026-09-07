"""
Tests para el super admin: acceso total, CRUD de cuentas y aislamiento.
"""
import pytest


def _venue_payload(name, username):
    return {
        "name": name,
        "admin_username": username,
        "admin_password": "pass123",
    }


class TestSuperAdmin:
    """Suite de tests para el super admin."""

    async def test_super_login(self, client, super_headers):
        """Login como super retorna rol superadmin sin venue."""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "test_super",
            "password": "superpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "superadmin"
        assert data["venue_id"] is None

    async def test_venue_login_has_role(self, client, super_headers):
        """Login de local retorna rol venue."""
        await client.post("/api/v1/venues", json=_venue_payload("Role Bar", "role_admin"),
                          headers=super_headers)
        resp = await client.post("/api/v1/auth/login", json={
            "username": "role_admin",
            "password": "pass123",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "venue"

    async def test_create_venue_requires_super(self, client):
        """Crear cuentas sin super token → 401/403."""
        assert (await client.post("/api/v1/venues", json=_venue_payload("X", "x"))).status_code in (401, 403)

    async def test_super_crud_venue(self, client, super_headers):
        """Crear, renombrar y borrar cuenta como super."""
        # Crear
        create = await client.post("/api/v1/venues", json=_venue_payload("CRUD Bar", "crud_admin"),
                                   headers=super_headers)
        assert create.status_code == 201
        vid = create.json()["id"]

        # Renombrar (nombre del local)
        patch = await client.patch(f"/api/v1/super/venues/{vid}", json={"name": "CRUD Renombrado"},
                                   headers=super_headers)
        assert patch.status_code == 200
        assert patch.json()["name"] == "CRUD Renombrado"
        assert patch.json()["slug"] == "crud-renombrado"

        # Listar con stats
        listed = await client.get("/api/v1/super/venues", headers=super_headers)
        assert listed.status_code == 200
        names = [v["name"] for v in listed.json()]
        assert "CRUD Renombrado" in names

        # Borrar
        delete = await client.delete(f"/api/v1/super/venues/{vid}", headers=super_headers)
        assert delete.status_code == 204
        assert (await client.get(f"/api/v1/venues/{vid}")).status_code == 404

    async def test_super_manages_any_venue_queue(self, client, super_headers):
        """El super opera la cola de cualquier local."""
        create = await client.post("/api/v1/venues", json=_venue_payload("Q Bar", "q_admin"),
                                   headers=super_headers)
        vid = create.json()["id"]
        add = await client.post(f"/api/v1/queue/venue/{vid}/add", json={
            "youtube_id": "super_q_1", "device_fingerprint": "fp_super_q_01", "title": "SQ",
        })
        assert add.status_code == 201
        item_id = add.json()["id"]

        # Mover y reproducir con token super
        move = await client.post(f"/api/v1/queue/venue/{vid}/move",
                                 json={"item_id": item_id, "new_position": 1},
                                 headers=super_headers)
        assert move.status_code == 200
        play = await client.post(f"/api/v1/queue/venue/{vid}/play/{item_id}", headers=super_headers)
        assert play.status_code == 200

    async def test_venue_admin_cannot_use_super(self, client, super_headers):
        """Un admin de local no entra a /super/* ni a otro local."""
        v1 = (await client.post("/api/v1/venues", json=_venue_payload("Iso One", "iso_one"),
                                headers=super_headers)).json()["id"]
        v2 = (await client.post("/api/v1/venues", json=_venue_payload("Iso Two", "iso_two"),
                                headers=super_headers)).json()["id"]
        login = await client.post("/api/v1/auth/login", json={"username": "iso_one", "password": "pass123"})
        H = {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert (await client.get("/api/v1/super/venues", headers=H)).status_code == 403
        assert (await client.patch(f"/api/v1/venues/{v2}", json={"name": "Hack"}, headers=H)).status_code == 403
        assert (await client.get(f"/api/v1/venues/{v2}/qr", headers=H)).status_code == 403
        # Pero sí su propio local
        assert (await client.get(f"/api/v1/venues/{v1}/qr", headers=H)).status_code == 200

    async def test_super_password_reset(self, client, super_headers):
        """El super puede resetear la clave de una cuenta."""
        create = await client.post("/api/v1/venues", json=_venue_payload("Reset Bar", "reset_admin"),
                                   headers=super_headers)
        vid = create.json()["id"]
        patch = await client.patch(f"/api/v1/super/venues/{vid}", json={"admin_password": "nueva123"},
                                   headers=super_headers)
        assert patch.status_code == 200
        # Login viejo falla, nuevo funciona
        old = await client.post("/api/v1/auth/login", json={"username": "reset_admin", "password": "pass123"})
        assert old.status_code == 401
        new = await client.post("/api/v1/auth/login", json={"username": "reset_admin", "password": "nueva123"})
        assert new.status_code == 200
