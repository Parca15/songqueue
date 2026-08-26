"""
Router WebSocket para sincronización en tiempo real.
Gestiona conexiones de clientes, reproductores y admins.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

router = APIRouter()


class ConnectionManager:
    """Gestiona conexiones WebSocket por local."""

    def __init__(self):
        # {venue_id: {websocket: {"role": str, "device_id": str}}}
        self.active_connections: Dict[int, Dict[WebSocket, dict]] = {}

    async def connect(self, websocket: WebSocket, venue_id: int):
        """Acepta una nueva conexión WebSocket."""
        await websocket.accept()
        if venue_id not in self.active_connections:
            self.active_connections[venue_id] = {}
        self.active_connections[venue_id][websocket] = {
            "role": "client",
            "device_id": "",
        }

    def disconnect(self, websocket: WebSocket, venue_id: int):
        """Desconecta un WebSocket."""
        if venue_id in self.active_connections:
            self.active_connections[venue_id].pop(websocket, None)
            if not self.active_connections[venue_id]:
                del self.active_connections[venue_id]

    def update_role(self, websocket: WebSocket, venue_id: int, role: str, device_id: str = ""):
        """Actualiza el rol de una conexión."""
        if venue_id in self.active_connections and websocket in self.active_connections[venue_id]:
            self.active_connections[venue_id][websocket] = {
                "role": role,
                "device_id": device_id,
            }

    async def broadcast_to_venue(self, venue_id: int, message: dict, role: str | None = None):
        """Envía un mensaje a todos los clientes de un local (opcionalmente filtrado por rol)."""
        if venue_id not in self.active_connections:
            return
        disconnected = []
        for ws, info in list(self.active_connections[venue_id].items()):
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

    async def send_to_admins(self, venue_id: int, message: dict):
        """Envía un mensaje solo a los admins de un local."""
        await self.broadcast_to_venue(venue_id, message, role="admin")

    def get_connection_count(self, venue_id: int) -> int:
        """Retorna el número de conexiones activas en un local."""
        return len(self.active_connections.get(venue_id, {}))

    def get_connections_by_role(self, venue_id: int, role: str) -> list:
        """Retorna las conexiones de un rol específico."""
        if venue_id not in self.active_connections:
            return []
        return [ws for ws, info in self.active_connections[venue_id].items() if info.get("role") == role]


manager = ConnectionManager()


@router.websocket("/venue/{venue_id}")
async def venue_websocket(websocket: WebSocket, venue_id: int):
    """
    WebSocket principal para un local.
    Protocolo:
      1. Cliente se conecta
      2. Cliente envía: {"action": "register", "role": "client|player|admin", "device_id": "..."}
      3. Servidor responde: {"type": "registered", "venue_id": ...}
      4. El servidor puede enviar: {"type": "queue_updated", "data": {...}}
                             {"type": "now_playing", "data": {...}}
                             {"type": "player_command", "command": "play|pause|skip"}
    """
    await manager.connect(websocket, venue_id)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "register":
                role = data.get("role", "client")
                device_id = data.get("device_id", "")
                manager.update_role(websocket, venue_id, role, device_id)
                await websocket.send_json({
                    "type": "registered",
                    "venue_id": venue_id,
                    "role": role,
                    "connections": manager.get_connection_count(venue_id),
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

            elif action == "player_command":
                # Comando del admin al reproductor
                await manager.send_to_player(venue_id, {
                    "type": "player_command",
                    "command": data.get("command"),
                    "data": data.get("data", {}),
                })

            elif action == "ping":
                await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})

            elif action == "get_stats":
                await websocket.send_json({
                    "type": "stats",
                    "venue_id": venue_id,
                    "total_connections": manager.get_connection_count(venue_id),
                    "players": len(manager.get_connections_by_role(venue_id, "player")),
                    "admins": len(manager.get_connections_by_role(venue_id, "admin")),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, venue_id)
    except Exception:
        manager.disconnect(websocket, venue_id)
