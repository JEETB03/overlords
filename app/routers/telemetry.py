import asyncio
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.simulator import simulator
from app.models import TelemetryData

logger = logging.getLogger("overlord.telemetry")
router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Active WebSocket connections
active_connections: list[WebSocket] = []

async def broadcast_ws(message: Dict[str, Any]):
    dead_connections = []
    text_data = json.dumps(message)
    for ws in active_connections:
        try:
            await ws.send_text(text_data)
        except Exception:
            dead_connections.append(ws)
    for ws in dead_connections:
        if ws in active_connections:
            active_connections.remove(ws)

# Register simulator callbacks
simulator.subscribe_telemetry(broadcast_ws)
simulator.subscribe_alerts(broadcast_ws)

@router.get("")
async def get_latest_telemetry():
    """Returns current telemetry state of UAV and UGV."""
    return {
        "uav": simulator.uav,
        "ugv": simulator.ugv,
        "geofence_status": simulator.uav.get("geofence_status", "INSIDE")
    }

@router.post("")
async def ingest_external_telemetry(data: TelemetryData):
    """Allows external drone companion computers to post telemetry."""
    target_dict = simulator.uav if data.drone_type == "UAV" else simulator.ugv
    target_dict.update({
        "lat": data.lat,
        "lon": data.lon,
        "altitude": data.altitude,
        "heading": data.heading,
        "speed": data.speed,
        "battery": data.battery,
        "mode": data.mode,
        "pitch": data.pitch,
        "roll": data.roll,
        "satellites": data.satellites,
        "rssi": data.rssi
    })
    return {"status": "SUCCESS", "drone_id": data.drone_id}

@router.websocket("/ws")
async def telemetry_websocket(websocket: WebSocket):
    """Live bi-directional telemetry and alert stream."""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(active_connections)}")
    
    # Send initial state immediately
    try:
        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "uav": simulator.uav,
            "ugv": simulator.ugv,
            "waypoints": simulator.waypoints,
            "polygon": simulator.active_polygon
        }))
        while True:
            # Keep-alive and listen for client commands
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
