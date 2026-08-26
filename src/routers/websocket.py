"""
Router WebSocket para sincronización en tiempo real.
Gestiona conexiones de clientes, reproductores y admins.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

router = APIRouter()

# Estructura: {venue_id: {websocket: {"role": str, "device_id": str}}}
class ConnectionManager:
    """Gestiona conexiones WebSocket por local."""

    def __init__(self):
        self.active_connections: Dict[int, Dict[WebSocket, dict]] = {}

    async def connect(self, websocket: WebSocket, venue_id: int, role: str = "client", device_id: str = ""):
        """Acepta una nueva conexión WebSocket."""
        await websocket.accept()
        if venue_id not in self.active_connections:
            self.active_connections[venue_id] = {}
        self.active_connections[venue_id][websocket] = {
            "role": role,
            "device_id": device_id,
        }

    def disconnect(self, websocket: WebSocket, venue_id: int):
        """Desconecta un WebSocket."""
        if venue_id in self.active_connections:
            self.active_connections[venue_id].pop(websocket, None)
            if not self.active_connections[venue_id]:
                del self.active_connections[venue_id]

    async def broadcast_to_venue(self, venue_id: int, message: dict, role: str | None = None):
        """Envía un mensaje a todos los clientes de un local (opcionalmente filtrado por rol)."""
        if venue_id not in self.active_connections:
            return
        disconnected = []
        for ws, info in self.active_connections[venue_id].items():
            if role is None or info.get("role") == role:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
        # Limpiar conexiones rotas
        for ws in disconnected:
            self.disconnect(ws, venue_id)

    async def send_to_player(self, venue_id: int, message: dict):
        """Envía un mensaje solo al reproductor de un local."""
        await self.broadcast_to_venue(venue_id, message, role="player")

    def get_connection_count(self, venue_id: int) -> int:
        """Retorna el número de conexiones activas en un local."""
        return len(self.active_connections.get(venue_id, {}))


manager = ConnectionManager()


@router.websocket("/venue/{venue_id}")
async def venue_websocket(websocket: WebSocket, venue_id: int):
    """
    WebSocket principal para un local.
    Los clientes se conectan y reciben actualizaciones de la cola en tiempo real.
    """
    # El cliente debe enviar su rol en el primer mensaje
    await manager.connect(websocket, venue_id)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "register":
                role = data.get("role", "client")
                device_id = data.get("device_id", "")
                manager.active_connections[venue_id][websocket] = {
                    "role": role,
                    "device_id": device_id,
                }
                await websocket.send_json({
                    "type": "registered",
                    "venue_id": venue_id,
                    "role": role,
                })

            elif action == "queue_update":
                # Broadcast de actualización de cola a todos los clientes del local
                await manager.broadcast_to_venue(venue_id, {
                    "type": "queue_updated",
                    "data": data.get("queue", {}),
                })

            elif action == "now_playing":
                # Informar a todos que cambió la canción actual
                await manager.broadcast_to_venue(venue_id, {
                    "type": "now_playing",
                    "data": data.get("song", {}),
                })

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, venue_id)
    except Exception:
        manager.disconnect(websocket, venue_id)
