"""
Tests para el router de Queue.
"""
import uuid

import pytest


def _uniq(prefix: str) -> str:
    """Nombre único por test (la BD se comparte en la sesión)."""
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


class TestQueue:
    """Suite de tests para gestion de colas."""

    async def _setup_venue_and_song(self, client, super_headers):
        """Helper: Crea venue (entrada directa, sin aprobación), hace login, y crea cancion."""
        username = _uniq("admin_q")
        venue_resp = await client.post("/api/v1/venues", json={
            "name": _uniq("Queue Test Venue"),
            "admin_username": username,
            "admin_password": "pass123",
            "max_songs_per_device": 2,
            "max_queue_size": 10,
            "require_approval": False,
        }, headers=super_headers)
        assert venue_resp.status_code == 201, venue_resp.text
        venue_id = venue_resp.json()["id"]

        login_resp = await client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "pass123",
        })
        token = login_resp.json()["access_token"]

        song_yt = _uniq("qsong")
        song_resp = await client.post("/api/v1/songs", json={
            "youtube_id": song_yt,
            "title": "Queue Song 1",
        })
        song_id = song_resp.json()["id"]

        return venue_id, token, song_id, song_yt

    async def test_get_queue_state_empty(self, client, super_headers):
        venue_resp = await client.post("/api/v1/venues", json={
            "name": "Empty Queue",
            "admin_username": "admin_empty",
            "admin_password": "pass123",
        }, headers=super_headers)
        venue_id = venue_resp.json()["id"]
        response = await client.get(f"/api/v1/queue/venue/{venue_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["venue_id"] == venue_id
        assert data["now_playing"] is None
        assert data["total_pending"] == 0

    async def test_add_to_queue(self, client, super_headers):
        venue_id, token, song_id, song_yt = await self._setup_venue_and_song(client, super_headers)
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt,
            "requested_by": "Test User",
            "device_fingerprint": "fp_test_123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["venue_id"] == venue_id
        assert data["status"] == "pending"
        assert data["song"]["title"] == "Queue Song 1"

    async def test_add_to_queue_limit(self, client, super_headers):
        venue_id, token, song_id, song_yt = await self._setup_venue_and_song(client, super_headers)
        await client.post("/api/v1/songs", json={"youtube_id": "queue_song_2", "title": "Queue Song 2"})
        await client.post("/api/v1/songs", json={"youtube_id": "queue_song_3", "title": "Queue Song 3"})

        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt, "device_fingerprint": "fp_limit_test",
        })
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_2", "device_fingerprint": "fp_limit_test",
        })
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_3", "device_fingerprint": "fp_limit_test",
        })
        assert response.status_code == 429

    async def test_add_duplicate_song(self, client, super_headers):
        venue_id, token, song_id, song_yt = await self._setup_venue_and_song(client, super_headers)
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt, "device_fingerprint": "fp_dup_0001",
        })
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt, "device_fingerprint": "fp_dup_0002",
        })
        assert response.status_code == 409

    async def test_remove_requires_auth(self, client, super_headers):
        venue_id, token, song_id, song_yt = await self._setup_venue_and_song(client, super_headers)
        add_resp = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt, "device_fingerprint": "fp_remove_01",
        })
        item_id = add_resp.json()["id"]
        # Sin auth
        response = await client.delete(f"/api/v1/queue/venue/{venue_id}/item/{item_id}")
        assert response.status_code == 401
        # Con auth
        response = await client.delete(
            f"/api/v1/queue/venue/{venue_id}/item/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

    async def test_play_and_skip(self, client, super_headers):
        venue_id, token, song_id, song_yt = await self._setup_venue_and_song(client, super_headers)
        await client.post("/api/v1/songs", json={"youtube_id": "play_song_2", "title": "Play Song 2"})

        resp1 = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": song_yt, "device_fingerprint": "fp_play_0001",
        })
        item1_id = resp1.json()["id"]
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "play_song_2", "device_fingerprint": "fp_play_0002",
        })

        play_resp = await client.post(
            f"/api/v1/queue/venue/{venue_id}/play/{item1_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert play_resp.status_code == 200
        assert play_resp.json()["status"] == "playing"

        skip_resp = await client.post(
            f"/api/v1/queue/venue/{venue_id}/skip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert skip_resp.status_code == 200


class TestWaiting:
    """Suite de tests para la lista de espera y nombres de cliente."""

    async def _setup_approval_venue(self, client, super_headers):
        """Venue con require_approval activado (default) + token admin."""
        username = _uniq("admin_w")
        venue_resp = await client.post("/api/v1/venues", json={
            "name": _uniq("Waiting Venue"),
            "admin_username": username,
            "admin_password": "pass123",
            "max_songs_per_device": 5,
            "max_queue_size": 20,
        }, headers=super_headers)
        assert venue_resp.status_code == 201, venue_resp.text
        venue_id = venue_resp.json()["id"]
        assert venue_resp.json()["require_approval"] is True
        login = await client.post("/api/v1/auth/login", json={
            "username": username, "password": "pass123",
        })
        return venue_id, {"Authorization": f"Bearer {login.json()['access_token']}"}

    async def test_add_goes_to_waiting_by_default(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        resp = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0001",
            "requested_by": "Carlos", "title": "Waiting Song",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "waiting"

    async def test_waiting_hidden_from_queue_state(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0002", "title": "S",
        })
        state = (await client.get(f"/api/v1/queue/venue/{venue_id}")).json()
        assert state["total_pending"] == 0
        waiting = (await client.get(f"/api/v1/queue/venue/{venue_id}/waiting", headers=H)).json()
        assert waiting["total_waiting"] == 1

    async def test_approve_first_and_last(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        yt1, yt2 = _uniq("wyt"), _uniq("wyt")
        r1 = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": yt1, "device_fingerprint": "fp_wait_0003", "requested_by": "Carlos", "title": "S1",
        })
        r2 = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": yt2, "device_fingerprint": "fp_wait_0004", "requested_by": "Ana", "title": "S2",
        })
        await client.post(f"/api/v1/queue/venue/{venue_id}/waiting/{r1.json()['id']}/approve",
                          json={"position": "last"}, headers=H)
        await client.post(f"/api/v1/queue/venue/{venue_id}/waiting/{r2.json()['id']}/approve",
                          json={"position": "first"}, headers=H)
        state = (await client.get(f"/api/v1/queue/venue/{venue_id}")).json()
        assert [x["requested_by"] for x in state["upcoming"]] == ["Ana", "Carlos"]
        missing = await client.post(f"/api/v1/queue/venue/{venue_id}/waiting/999999/approve",
                                    json={"position": "last"}, headers=H)
        assert missing.status_code == 404

    async def test_reject_waiting(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        r = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0005", "title": "S",
        })
        item_id = r.json()["id"]
        rej = await client.post(f"/api/v1/queue/venue/{venue_id}/waiting/{item_id}/reject", headers=H)
        assert rej.status_code == 200
        waiting = (await client.get(f"/api/v1/queue/venue/{venue_id}/waiting", headers=H)).json()
        assert waiting["total_waiting"] == 0

    async def test_waiting_mine(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0006",
            "requested_by": "Carlos", "title": "S",
        })
        mine = (await client.get(
            f"/api/v1/queue/venue/{venue_id}/waiting/mine",
            params={"device_fingerprint": "fp_wait_0006"},
        )).json()
        assert mine["total_waiting"] == 1
        assert mine["waiting"][0]["requested_by"] == "Carlos"
        other = (await client.get(
            f"/api/v1/queue/venue/{venue_id}/waiting/mine",
            params={"device_fingerprint": "fp_wait_0000"},
        )).json()
        assert other["total_waiting"] == 0

    async def test_register_name_duplicate(self, client, super_headers):
        venue_id, H = await self._setup_approval_venue(client, super_headers)
        ok = await client.post(f"/api/v1/venues/{venue_id}/register-name", json={
            "display_name": "Carlos", "device_fingerprint": "fp_wait_0007",
        })
        assert ok.status_code == 201
        dup = await client.post(f"/api/v1/venues/{venue_id}/register-name", json={
            "display_name": "carlos", "device_fingerprint": "fp_wait_0008",
        })
        assert dup.status_code == 409
        assert "ya está en uso" in dup.json()["detail"]

    async def test_waiting_counts_toward_device_limit(self, client, super_headers):
        username = _uniq("admin_wl")
        venue_resp = await client.post("/api/v1/venues", json={
            "name": _uniq("Waiting Limit"),
            "admin_username": username,
            "admin_password": "pass123",
            "max_songs_per_device": 1,
            "max_queue_size": 20,
        }, headers=super_headers)
        venue_id = venue_resp.json()["id"]
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0009", "title": "S1",
        })
        second = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": _uniq("wyt"), "device_fingerprint": "fp_wait_0009", "title": "S2",
        })
        assert second.status_code == 429
