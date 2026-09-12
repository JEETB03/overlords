import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models import GeofenceCreate, GeofenceResponse
from app.services.geofence_planner import (
    generate_lawnmower_path,
    calculate_polygon_area_sqm
)
from app.services.simulator import simulator
from app.database import save_geofence, get_active_geofence

router = APIRouter(prefix="/geofence", tags=["geofence"])

@router.post("/generate-path")
async def generate_path(req: GeofenceCreate):
    """Calculates boustrophedon lawnmower search waypoints for a given polygon."""
    if len(req.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices")

    area_sqm = calculate_polygon_area_sqm(req.polygon)
    waypoints, distance_m, duration_sec = generate_lawnmower_path(
        polygon=req.polygon,
        lane_spacing_meters=req.lane_spacing_meters,
        altitude_meters=req.altitude_meters
    )

    return {
        "status": "SUCCESS",
        "area_sqm": round(area_sqm, 1),
        "area_hectares": round(area_sqm / 10000.0, 2),
        "total_distance_meters": round(distance_m, 1),
        "estimated_duration_sec": round(duration_sec, 0),
        "waypoints_count": len(waypoints),
        "waypoints": waypoints
    }

@router.post("/upload")
async def upload_and_dispatch_geofence(req: GeofenceCreate):
    """Saves geofence to database and uploads autonomous traversal waypoints to UAV."""
    if len(req.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices")

    area_sqm = calculate_polygon_area_sqm(req.polygon)
    waypoints, distance_m, duration_sec = generate_lawnmower_path(
        polygon=req.polygon,
        lane_spacing_meters=req.lane_spacing_meters,
        altitude_meters=req.altitude_meters
    )

    # Save to DB
    record = await save_geofence(
        name=req.name,
        polygon_coords=req.polygon,
        traversal_path=waypoints,
        area_sqm=area_sqm,
        duration_sec=duration_sec
    )

    # Dispatch to UAV Simulator
    simulator.set_mission(req.polygon, waypoints)
    
    # Broadcast alert
    await simulator.emit_alert(
        severity="INFO",
        title="AUTONOMOUS GEOFENCE MISSION DISPATCHED",
        message=f"Uploaded {len(waypoints)} lawnmower waypoints ({round(area_sqm/10000, 2)} ha) to UAV-ALPHA.",
        drone_id="UAV-ALPHA",
        data={"geofence_id": record.id, "waypoints_count": len(waypoints)}
    )

    return {
        "status": "DISPATCHED",
        "geofence_id": record.id,
        "name": record.name,
        "area_sqm": area_sqm,
        "waypoints": waypoints
    }

@router.get("/active")
async def get_current_geofence():
    """Fetches the active geofence and traversal mission."""
    record = await get_active_geofence()
    if not record:
        return {"active": False, "polygon": [], "waypoints": []}

    return {
        "active": True,
        "id": record.id,
        "name": record.name,
        "polygon": json.loads(record.polygon_geojson),
        "waypoints": json.loads(record.traversal_path_geojson) if record.traversal_path_geojson else [],
        "area_sqm": record.area_sqm,
        "created_at": record.created_at.isoformat()
    }
