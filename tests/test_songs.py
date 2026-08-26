"""
Tests para el router de Songs.
"""
import pytest


class TestSongs:
    """Suite de tests para gestión de canciones."""

    async def test_create_song(self, client):
        """Test: Crear una canción."""
        response = await client.post("/api/v1/songs", json={
            "youtube_id": "test123abc",
            "title": "Test Song",
            "channel": "Test Channel",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "duration_seconds": 180,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["youtube_id"] == "test123abc"
        assert data["title"] == "Test Song"

    async def test_create_song_duplicate(self, client):
        """Test: No duplicar canción con mismo youtube_id."""
        song_data = {
            "youtube_id": "dup123",
            "title": "Duplicate Song",
        }
        await client.post("/api/v1/songs", json=song_data)
        response = await client.post("/api/v1/songs", json=song_data)
        # Debe retornar la existente, no error
        assert response.status_code == 201

    async def test_get_song(self, client):
        """Test: Obtener canción por ID."""
        create_resp = await client.post("/api/v1/songs", json={
            "youtube_id": "get456",
            "title": "Get Song",
        })
        song_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/songs/{song_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Song"

    async def test_get_song_not_found(self, client):
        """Test: Canción no encontrada."""
        response = await client.get("/api/v1/songs/99999")
        assert response.status_code == 404
