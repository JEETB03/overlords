import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.lora_link_service import lora_link_service
from app.config import settings

# ---------------------------------------------------------
# Pydantic Schemas matching LoRa Link API & Tactical C2
# ---------------------------------------------------------
class MissionSummary(BaseModel):
    mission_id: str = Field(..., description="Unique mission identifier, e.g. LL-20260913-025953-11E1")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when packet reassembly completed")
    image_filename: Optional[str] = Field(None, description="Filename of reconstructed JPEG image")
    json_filename: Optional[str] = Field(None, description="Filename of mission telemetry metadata")
    image_size: Optional[int] = Field(None, description="Reconstructed image file size in bytes")
    json_size: Optional[int] = Field(None, description="Metadata JSON size in bytes")
    image_url: str = Field(..., description="Endpoint path to fetch binary image bytes")
    metadata_url: str = Field(..., description="Endpoint path to fetch metadata JSON")

class MissionDetail(BaseModel):
    mission_id: str = Field(..., description="Unique mission identifier")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when packet reassembly completed")
    image_filename: Optional[str] = Field(None, description="Filename of reconstructed JPEG image")
    json_filename: Optional[str] = Field(None, description="Filename of mission telemetry metadata")
    image_size: Optional[int] = Field(None, description="Reconstructed image file size in bytes")
    json_size: Optional[int] = Field(None, description="Metadata JSON size in bytes")
    image_url: str = Field(..., description="Endpoint path to fetch binary image bytes")
    metadata_url: str = Field(..., description="Endpoint path to fetch metadata JSON")
    metadata: Dict[str, Any] = Field(..., description="Raw drone mission metadata (lat, lon, camera, operator, drone ID)")

class ReconWaypoint(BaseModel):
    seq: int = Field(..., description="Sequential flight waypoint order index (1, 2, ...)")
    label: str = Field(..., description="Tactical waypoint label, e.g. M1, M2, M3")
    mission_id: str = Field(..., description="Unique mission ID")
    completed_at: str = Field(..., description="Completion timestamp formatted as string")
    lat: float = Field(..., description="Survey waypoint latitude coordinate")
    lon: float = Field(..., description="Survey waypoint longitude coordinate")
    altitude: float = Field(0.0, description="Altitude in meters")
    image_filename: str = Field(..., description="Image filename")
    image_url: str = Field(..., description="Snapshot image API path")
    camera: str = Field("RunCam", description="Onboard camera payload name")
    operator: str = Field("GROUND-STATION", description="Mission dispatcher operator")
    mission_type: str = Field("SURVEY", description="Operational mission type")
    image_size: int = Field(..., description="Image size in bytes")
    dimensions: str = Field("1024x1024", description="Image resolution dimensions")

class LoRaLinkStatus(BaseModel):
    online: bool = Field(..., description="True if remote LoRa Link RX API is reachable")
    base_url: str = Field(..., description="Configured URL of the hardware RX ground station")
    detail: Dict[str, Any] = Field(..., description="Health check details including pc_root and state_file_exists")
    synced_count: int = Field(..., description="Total count of cached missions")
    last_sync_time: float = Field(..., description="Unix epoch timestamp of last sync check")

class SyncResult(BaseModel):
    status: str = Field(..., description="Sync operation status: SUCCESS or OFFLINE")
    synced_new: Optional[int] = Field(0, description="Count of newly discovered and ingested missions")
    total_remote: Optional[int] = Field(0, description="Total missions available on remote station")
    last_sync: Optional[str] = Field(None, description="Formatted time string of sync")
    message: Optional[str] = Field(None, description="Status detail message if any")

# ---------------------------------------------------------
# Router Endpoints
# ---------------------------------------------------------
router = APIRouter(prefix="/lora-link", tags=["lora-link"])

@router.get("/status", response_model=LoRaLinkStatus, summary="LoRa Link RX Station Health")
async def get_lora_link_status():
    """
    Returns connectivity status and file repository health of the external
    LoRa Link Hardware RX Ground Station (serving at `http://172.16.59.210:8000`).
    """
    health = await lora_link_service.check_health()
    return {
        "online": lora_link_service.is_online,
        "base_url": lora_link_service.base_url,
        "detail": health,
        "synced_count": len(lora_link_service.synced_mission_ids),
        "last_sync_time": lora_link_service.last_sync_time
    }

@router.get("/missions", response_model=List[MissionSummary], summary="List Completed LoRa Missions")
async def list_lora_link_missions(
    limit: int = Query(50, ge=1, le=100, description="Max missions to return (most recent first by default)"),
    order: str = Query("desc", pattern="^(desc|asc)$", description="'desc' (newest first) or 'asc' (oldest first)")
):
    """
    List completed missions retrieved from the LoRa Link hardware RX API.
    Poll this endpoint to discover new missions as they land over long-range radio.
    """
    return await lora_link_service.fetch_missions(limit=limit, order=order)

@router.get("/missions/latest", response_model=MissionDetail, summary="Latest Landed LoRa Mission")
async def get_latest_lora_link_mission():
    """
    Return the most recently completed mission, including reconstructed image URLs
    and embedded telemetry metadata (lat, lon, altitude, camera, operator).
    """
    mission = await lora_link_service.fetch_latest_mission()
    if not mission:
        raise HTTPException(status_code=404, detail="No mission found on remote LoRa station")
    return mission

@router.get("/missions/{mission_id}", response_model=MissionDetail, summary="Get LoRa Mission Details")
async def get_lora_link_mission_detail(
    mission_id: str = Path(..., description="Unique LoRa mission ID, e.g. 'LL-20260913-025953-11E1'")
):
    """
    Returns full metadata and file links for one specific LoRa survey mission.
    """
    detail = await lora_link_service.fetch_mission_detail(mission_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return detail

@router.get("/missions/{mission_id}/metadata", summary="Get Raw Mission Metadata JSON")
async def get_lora_link_mission_metadata(
    mission_id: str = Path(..., description="Unique LoRa mission ID, e.g. 'LL-20260913-025953-11E1'")
):
    """
    Raw metadata.json content only (timestamp, lat/lon, drone info, camera payload, etc.).
    """
    metadata = await lora_link_service.fetch_mission_metadata(mission_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Metadata for mission {mission_id} not found")
    return metadata

@router.get("/track", response_model=List[ReconWaypoint], summary="Get Chronological LoRa Recon Flight Track")
async def get_lora_link_recon_track():
    """
    Returns chronologically ordered GPS flight trail and waypoint corridor
    (M1, M2, M3, ...) reconstructed from all completed LoRa survey missions.
    """
    return await lora_link_service.get_recon_track()

@router.post("/sync", response_model=SyncResult, summary="Trigger Manual LoRa RX Sync")
async def trigger_lora_link_sync():
    """
    Manually triggers immediate synchronization with the external LoRa Link API,
    caches new images locally, and dispatches tactical C2 alerts.
    """
    return await lora_link_service.sync_missions()

@router.get("/image/{mission_id}", summary="Get Reconstructed LoRa Mission Image")
async def get_lora_link_image(
    mission_id: str = Path(..., description="Unique LoRa mission ID, e.g. 'LL-20260913-025953-11E1'")
):
    """
    Serves cached mission image (JPEG) or downloads on-demand from the remote LoRa station.
    """
    # Check local snapshot cache
    local_files = [
        settings.SNAPSHOT_DIR / f"{mission_id}.jpg",
        settings.SNAPSHOT_DIR / f"{mission_id}.jpeg"
    ]
    for p in local_files:
        if p.exists() and p.stat().st_size > 0:
            return FileResponse(str(p), media_type="image/jpeg")

    # Download from remote station
    downloaded_path = await lora_link_service.download_and_cache_image(mission_id)
    if downloaded_path and os.path.exists(downloaded_path):
        return FileResponse(downloaded_path, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Image could not be retrieved from LoRa Link station")
