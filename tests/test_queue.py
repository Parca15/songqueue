"""
Tests para el router de Queue.
"""
import pytest


class TestQueue:
    """Suite de tests para gestion de colas."""

    async def _setup_venue_and_song(self, client):
        """Helper: Crea venue, hace login, y crea cancion."""
        venue_resp = await client.post("/api/v1/venues", json={
            "name": "Queue Test Venue",
            "admin_username": "admin_q",
            "admin_password": "pass123",
            "max_songs_per_device": 2,
            "max_queue_size": 10,
        })
        venue_id = venue_resp.json()["id"]

        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "admin_q",
            "password": "pass123",
        })
        token = login_resp.json()["access_token"]

        song_resp = await client.post("/api/v1/songs", json={
            "youtube_id": "queue_song_1",
            "title": "Queue Song 1",
        })
        song_id = song_resp.json()["id"]

        return venue_id, token, song_id

    async def test_get_queue_state_empty(self, client):
        venue_resp = await client.post("/api/v1/venues", json={
            "name": "Empty Queue",
            "admin_username": "admin_empty",
            "admin_password": "pass123",
        })
        venue_id = venue_resp.json()["id"]
        response = await client.get(f"/api/v1/queue/venue/{venue_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["venue_id"] == venue_id
        assert data["now_playing"] is None
        assert data["total_pending"] == 0

    async def test_add_to_queue(self, client):
        venue_id, token, song_id = await self._setup_venue_and_song(client)
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "requested_by": "Test User",
            "device_fingerprint": "fp_test_123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["venue_id"] == venue_id
        assert data["status"] == "pending"
        assert data["song"]["title"] == "Queue Song 1"

    async def test_add_to_queue_limit(self, client):
        venue_id, token, song_id = await self._setup_venue_and_song(client)
        await client.post("/api/v1/songs", json={"youtube_id": "queue_song_2", "title": "Queue Song 2"})
        await client.post("/api/v1/songs", json={"youtube_id": "queue_song_3", "title": "Queue Song 3"})

        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1", "device_fingerprint": "fp_limit_test",
        })
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_2", "device_fingerprint": "fp_limit_test",
        })
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_3", "device_fingerprint": "fp_limit_test",
        })
        assert response.status_code == 429

    async def test_add_duplicate_song(self, client):
        venue_id, token, song_id = await self._setup_venue_and_song(client)
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1", "device_fingerprint": "fp_dup_1",
        })
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1", "device_fingerprint": "fp_dup_2",
        })
        assert response.status_code == 409

    async def test_remove_requires_auth(self, client):
        venue_id, token, song_id = await self._setup_venue_and_song(client)
        add_resp = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1", "device_fingerprint": "fp_remove",
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

    async def test_play_and_skip(self, client):
        venue_id, token, song_id = await self._setup_venue_and_song(client)
        await client.post("/api/v1/songs", json={"youtube_id": "play_song_2", "title": "Play Song 2"})

        resp1 = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1", "device_fingerprint": "fp_play",
        })
        item1_id = resp1.json()["id"]
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "play_song_2", "device_fingerprint": "fp_play2",
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
