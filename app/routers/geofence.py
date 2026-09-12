import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models import GeofenceCreate, GeofenceResponse
from app.services.geofence_planner import (
    plan_uav_mission,
    plan_ugv_mission,
    calculate_polygon_area_sqm
)
from app.services.simulator import simulator
from app.database import save_geofence, get_active_geofence

router = APIRouter(prefix="/geofence", tags=["geofence"])

@router.post("/generate-path")
async def generate_path(req: GeofenceCreate):
    """Calculates UAV boustrophedon search and UGV perimeter patrol waypoints from last known locations."""
    if len(req.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices")

    area_sqm = calculate_polygon_area_sqm(req.polygon)

    # Use drone's current/last known positions as start coordinates if not explicitly passed
    uav_start = tuple(req.uav_start) if req.uav_start else (simulator.uav["lat"], simulator.uav["lon"])
    ugv_start = tuple(req.ugv_start) if req.ugv_start else (simulator.ugv["lat"], simulator.ugv["lon"])

    # 1. Plan UAV deployment from last known UAV location to geofence entry, then sweep grid
    uav_waypoints, uav_dist_m, uav_dur_sec, uav_meta = plan_uav_mission(
        polygon=req.polygon,
        uav_start=uav_start,
        lane_spacing_meters=req.lane_spacing_meters,
        altitude_meters=req.altitude_meters
    )

    # 2. Plan UGV deployment from last known UGV location to geofence perimeter, then patrol loop
    ugv_waypoints, ugv_dist_m, ugv_dur_sec, ugv_meta = plan_ugv_mission(
        polygon=req.polygon,
        ugv_start=ugv_start
    )

    return {
        "status": "SUCCESS",
        "area_sqm": round(area_sqm, 1),
        "area_hectares": round(area_sqm / 10000.0, 2),
        "uav_start": list(uav_start),
        "ugv_start": list(ugv_start),
        "uav_waypoints_count": len(uav_waypoints),
        "uav_waypoints": uav_waypoints,
        "uav_total_distance_meters": round(uav_dist_m, 1),
        "uav_estimated_duration_sec": round(uav_dur_sec, 0),
        "uav_meta": uav_meta,
        "ugv_waypoints_count": len(ugv_waypoints),
        "ugv_waypoints": ugv_waypoints,
        "ugv_total_distance_meters": round(ugv_dist_m, 1),
        "ugv_estimated_duration_sec": round(ugv_dur_sec, 0),
        "ugv_meta": ugv_meta,
        # Backwards compatible alias
        "waypoints": uav_waypoints,
        "total_distance_meters": round(uav_dist_m, 1),
        "estimated_duration_sec": round(uav_dur_sec, 0),
        "waypoints_count": len(uav_waypoints)
    }

@router.post("/upload")
async def upload_and_dispatch_geofence(req: GeofenceCreate):
    """Saves geofence to database and deploys both UAV and UGV to the new geofence from their last known locations."""
    if len(req.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices")

    area_sqm = calculate_polygon_area_sqm(req.polygon)

    uav_start = tuple(req.uav_start) if req.uav_start else (simulator.uav["lat"], simulator.uav["lon"])
    ugv_start = tuple(req.ugv_start) if req.ugv_start else (simulator.ugv["lat"], simulator.ugv["lon"])

    uav_waypoints, uav_dist_m, uav_dur_sec, uav_meta = plan_uav_mission(
        polygon=req.polygon,
        uav_start=uav_start,
        lane_spacing_meters=req.lane_spacing_meters,
        altitude_meters=req.altitude_meters
    )

    ugv_waypoints, ugv_dist_m, ugv_dur_sec, ugv_meta = plan_ugv_mission(
        polygon=req.polygon,
        ugv_start=ugv_start
    )

    # Store in database
    combined_mission = {
        "uav": uav_waypoints,
        "ugv": ugv_waypoints,
        "uav_meta": uav_meta,
        "ugv_meta": ugv_meta
    }
    record = await save_geofence(
        name=req.name,
        polygon_coords=req.polygon,
        traversal_path=combined_mission,
        area_sqm=area_sqm,
        duration_sec=uav_dur_sec
    )

    # Dispatch to UAV and UGV Simulator autopilots
    simulator.set_mission(req.polygon, uav_waypoints, ugv_waypoints)
    
    # Broadcast alert
    await simulator.emit_alert(
        severity="INFO",
        title="UAV & UGV DUAL DEPLOYMENT DISPATCHED",
        message=f"UAV deploying to grid ({len(uav_waypoints)} WPs). UGV deploying to perimeter ({len(ugv_waypoints)} WPs).",
        drone_id="C2-AUTOPILOT",
        data={
            "geofence_id": record.id,
            "uav_waypoints_count": len(uav_waypoints),
            "ugv_waypoints_count": len(ugv_waypoints)
        }
    )

    return {
        "status": "DISPATCHED",
        "geofence_id": record.id,
        "name": record.name,
        "area_sqm": area_sqm,
        "uav_waypoints": uav_waypoints,
        "ugv_waypoints": ugv_waypoints,
        "waypoints": uav_waypoints  # compatibility
    }

@router.get("/active")
async def get_current_geofence():
    """Fetches the active geofence and traversal mission."""
    record = await get_active_geofence()
    if not record:
        return {"active": False, "polygon": [], "waypoints": [], "uav_waypoints": [], "ugv_waypoints": []}

    path_data = json.loads(record.traversal_path_geojson) if record.traversal_path_geojson else {}
    uav_wps = path_data.get("uav", []) if isinstance(path_data, dict) else (path_data if isinstance(path_data, list) else [])
    ugv_wps = path_data.get("ugv", []) if isinstance(path_data, dict) else []

    return {
        "active": True,
        "id": record.id,
        "name": record.name,
        "polygon": json.loads(record.polygon_geojson),
        "uav_waypoints": uav_wps,
        "ugv_waypoints": ugv_wps,
        "waypoints": uav_wps,
        "area_sqm": record.area_sqm,
        "created_at": record.created_at.isoformat()
    }
