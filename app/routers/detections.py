import base64
import os
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel

from app.models import DetectionCreate
from app.database import (
    save_detection,
    get_all_detections,
    get_detection_by_id,
    update_detection_status
)
from app.config import settings
from app.services.simulator import simulator

router = APIRouter(prefix="/detections", tags=["detections"])

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

@router.get("")
async def list_detections(limit: int = 50):
    """Retrieves list of all recorded AI detections."""
    records = await get_all_detections(limit)
    out = []
    for r in records:
        ts_str = r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if r.timestamp else ""
        out.append({
            "id": r.id,
            "detection_id": r.id,
            "timestamp": ts_str,
            "drone_id": r.drone_id,
            "drone_type": r.drone_type,
            "target_type": r.target_type,
            "confidence": r.confidence,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "lat": r.latitude,
            "lon": r.longitude,
            "altitude": r.altitude,
            "image_url": f"/api/snapshots/{r.id}" if r.image_filename else None,
            "thumbnail_b64": r.thumbnail_b64[:100] + "..." if r.thumbnail_b64 else None,
            "lora_rssi": r.lora_rssi,
            "lora_snr": r.lora_snr,
            "lora_packets_received": r.lora_packets_received,
            "status": r.status,
            "notes": r.notes
        })
    return out

@router.get("/{detection_id}")
async def get_detection(detection_id: str):
    """Retrieves single detection details with coordinates, timestamp, and snapshot."""
    r = await get_detection_by_id(detection_id)
    if not r:
        raise HTTPException(status_code=404, detail="Detection not found")
    ts_str = r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if r.timestamp else ""
    return {
        "id": r.id,
        "detection_id": r.id,
        "timestamp": ts_str,
        "drone_id": r.drone_id,
        "drone_type": r.drone_type,
        "target_type": r.target_type,
        "confidence": r.confidence,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "lat": r.latitude,
        "lon": r.longitude,
        "altitude": r.altitude,
        "image_url": f"/api/snapshots/{r.id}" if r.image_filename else None,
        "lora_rssi": r.lora_rssi,
        "lora_snr": r.lora_snr,
        "lora_packets_received": r.lora_packets_received,
        "status": r.status,
        "notes": r.notes
    }

@router.post("")
async def create_detection(req: DetectionCreate):
    """Ingests an AI detection from drone onboard companion computer."""
    image_filename = None
    image_path = None
    
    if req.image_b64:
        # Decode and save snapshot
        raw_bytes = base64.b64decode(req.image_b64)
        image_filename = f"ext_detect_{int(os.times().elapsed*1000)}.jpg"
        image_path = str(settings.SNAPSHOT_DIR / image_filename)
        with open(image_path, "wb") as f:
            f.write(raw_bytes)

    record = await save_detection(
        drone_id=req.drone_id,
        drone_type=req.drone_type,
        target_type=req.target_type,
        confidence=req.confidence,
        latitude=req.lat,
        longitude=req.lon,
        altitude=req.altitude,
        image_filename=image_filename,
        image_path=image_path,
        thumbnail_b64=req.image_b64,
        lora_rssi=req.lora_rssi,
        lora_snr=req.lora_snr,
        notes=req.notes
    )

    # Broadcast alert
    severity = "TARGET_ACQUIRED" if "LIFE" in req.target_type.upper() else "WARNING"
    ts_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if record.timestamp else ""
    await simulator.emit_alert(
        severity=severity,
        title=f"AI DETECTION: {req.target_type}",
        message=f"{req.drone_id} acquired {req.target_type} ({int(req.confidence*100)}% conf) at ({req.lat:.5f}, {req.lon:.5f})",
        drone_id=req.drone_id,
        data={
            "id": record.id,
            "detection_id": record.id,
            "target_type": req.target_type,
            "lat": req.lat,
            "lon": req.lon,
            "latitude": req.lat,
            "longitude": req.lon,
            "altitude": req.altitude,
            "confidence": req.confidence,
            "timestamp": ts_str,
            "image_url": f"/api/snapshots/{record.id}",
            "lora_rssi": req.lora_rssi,
            "lora_snr": req.lora_snr,
            "drone_id": req.drone_id
        }
    )

    return {"status": "RECORDED", "id": record.id}

@router.patch("/{detection_id}/status")
async def update_status(detection_id: str, body: StatusUpdate):
    """Updates operational status of a detection (e.g. VERIFIED, DISPATCHED)."""
    record = await update_detection_status(detection_id, body.status, body.notes)
    if not record:
        raise HTTPException(status_code=404, detail="Detection not found")
    return {"status": "UPDATED", "detection_id": record.id, "new_status": record.status}
