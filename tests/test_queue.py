"""
Tests para el router de Queue.
"""
import pytest


class TestQueue:
    """Suite de tests para gestión de colas."""

    async def _create_venue_and_song(self, client):
        """Helper: Crea un local y una canción."""
        venue_resp = await client.post("/api/v1/venues", json={
            "name": "Queue Test Venue",
            "admin_username": "admin_q",
            "admin_password": "pass123",
            "max_songs_per_device": 2,
            "max_queue_size": 10,
        })
        venue_id = venue_resp.json()["id"]

        song_resp = await client.post("/api/v1/songs", json={
            "youtube_id": "queue_song_1",
            "title": "Queue Song 1",
        })
        song_id = song_resp.json()["id"]

        return venue_id, song_id

    async def test_get_queue_state_empty(self, client):
        """Test: Estado de cola vacía."""
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
        assert data["upcoming"] == []
        assert data["total_pending"] == 0

    async def test_add_to_queue(self, client):
        """Test: Agregar canción a la cola."""
        venue_id, song_id = await self._create_venue_and_song(client)

        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "requested_by": "Test User",
            "device_fingerprint": "fp_test_123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["venue_id"] == venue_id
        assert data["status"] == "pending"
        assert data["requested_by"] == "Test User"
        assert data["song"]["title"] == "Queue Song 1"

    async def test_add_to_queue_limit(self, client):
        """Test: Límite de canciones por dispositivo."""
        venue_id, song_id = await self._create_venue_and_song(client)

        # Crear otra canción
        await client.post("/api/v1/songs", json={
            "youtube_id": "queue_song_2",
            "title": "Queue Song 2",
        })
        await client.post("/api/v1/songs", json={
            "youtube_id": "queue_song_3",
            "title": "Queue Song 3",
        })

        # Agregar 2 canciones (límite)
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "device_fingerprint": "fp_limit_test",
        })
        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_2",
            "device_fingerprint": "fp_limit_test",
        })

        # Intentar agregar 3ra (debe fallar)
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_3",
            "device_fingerprint": "fp_limit_test",
        })
        assert response.status_code == 429

    async def test_add_duplicate_song(self, client):
        """Test: No permitir duplicados cuando allow_duplicates=False."""
        venue_id, song_id = await self._create_venue_and_song(client)

        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "device_fingerprint": "fp_dup_1",
        })

        response = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "device_fingerprint": "fp_dup_2",
        })
        assert response.status_code == 409

    async def test_remove_from_queue(self, client):
        """Test: Eliminar canción de la cola."""
        venue_id, song_id = await self._create_venue_and_song(client)

        add_resp = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "device_fingerprint": "fp_remove",
        })
        item_id = add_resp.json()["id"]

        response = await client.delete(f"/api/v1/queue/venue/{venue_id}/item/{item_id}")
        assert response.status_code == 204

    async def test_reorder_queue(self, client):
        """Test: Reordenar la cola."""
        venue_id, _ = await self._create_venue_and_song(client)

        # Crear más canciones
        for i in range(2, 4):
            await client.post("/api/v1/songs", json={
                "youtube_id": f"reorder_song_{i}",
                "title": f"Reorder Song {i}",
            })

        # Agregar 3 canciones
        items = []
        for i in range(1, 4):
            resp = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
                "youtube_id": f"reorder_song_{i}" if i > 1 else "queue_song_1",
                "device_fingerprint": f"fp_reorder_{i}",
            })
            items.append(resp.json()["id"])

        # Reordenar: invertir
        response = await client.post(f"/api/v1/queue/venue/{venue_id}/reorder", json={
            "item_ids": list(reversed(items)),
        })
        assert response.status_code == 200
        reordered = response.json()
        assert len(reordered) == 3

    async def test_play_and_skip(self, client):
        """Test: Marcar como playing y skip."""
        venue_id, _ = await self._create_venue_and_song(client)

        await client.post("/api/v1/songs", json={
            "youtube_id": "play_song_2",
            "title": "Play Song 2",
        })

        # Agregar 2 canciones
        resp1 = await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "queue_song_1",
            "device_fingerprint": "fp_play",
        })
        item1_id = resp1.json()["id"]

        await client.post(f"/api/v1/queue/venue/{venue_id}/add", json={
            "youtube_id": "play_song_2",
            "device_fingerprint": "fp_play2",
        })

        # Marcar primera como playing
        play_resp = await client.post(f"/api/v1/queue/venue/{venue_id}/play/{item1_id}")
        assert play_resp.status_code == 200
        assert play_resp.json()["status"] == "playing"

        # Skip
        skip_resp = await client.post(f"/api/v1/queue/venue/{venue_id}/skip")
        assert skip_resp.status_code == 200
