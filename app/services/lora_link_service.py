import asyncio
import base64
import datetime
import logging
import os
import time
from typing import Dict, Any, List, Optional, Set
import httpx

from app.config import settings
from app.database import save_detection, get_all_detections, get_detection_by_id
from app.services.simulator import simulator

logger = logging.getLogger("overlord.lora_link")

class LoRaLinkService:
    def __init__(self):
        self.base_url = settings.LORA_API_BASE_URL.rstrip("/")
        self.is_online = False
        self.last_health_check: float = 0.0
        self.last_sync_time: float = 0.0
        self.status_detail: Dict[str, Any] = {}
        self.synced_mission_ids: Set[str] = set()
        self.cached_missions: List[Dict[str, Any]] = []
        self.latest_mission: Optional[Dict[str, Any]] = None
        self._background_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def check_health(self) -> Dict[str, Any]:
        """Checks connection to the remote LoRa Link RX API."""
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    self.is_online = True
                    self.last_health_check = time.time()
                    self.status_detail = {
                        "online": True,
                        "status": data.get("status", "ok"),
                        "pc_root": data.get("pc_root"),
                        "state_file_exists": data.get("state_file_exists"),
                        "base_url": self.base_url,
                        "last_check": time.strftime("%H:%M:%S")
                    }
                    return self.status_detail
                else:
                    self.is_online = False
                    self.status_detail = {
                        "online": False,
                        "status": f"HTTP {resp.status_code}",
                        "base_url": self.base_url,
                        "last_check": time.strftime("%H:%M:%S")
                    }
                    return self.status_detail
        except Exception as e:
            self.is_online = False
            self.status_detail = {
                "online": False,
                "error": str(e),
                "base_url": self.base_url,
                "last_check": time.strftime("%H:%M:%S")
            }
            return self.status_detail

    async def fetch_missions(self, limit: int = 50, order: str = "desc") -> List[Dict[str, Any]]:
        """Fetches list of completed missions from the LoRa Link API."""
        url = f"{self.base_url}/missions"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
                resp = await client.get(url, params={"limit": limit, "order": order})
                if resp.status_code == 200:
                    missions = resp.json()
                    self.cached_missions = missions
                    return missions
                else:
                    logger.warning(f"Failed to fetch LoRa missions: HTTP {resp.status_code}")
                    return self.cached_missions
        except Exception as e:
            logger.debug(f"LoRa Link fetch missions exception: {e}")
            return self.cached_missions

    async def fetch_latest_mission(self) -> Optional[Dict[str, Any]]:
        """Fetches detail of the most recently landed LoRa mission."""
        url = f"{self.base_url}/missions/latest"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    self.latest_mission = data
                    return data
                return None
        except Exception as e:
            logger.debug(f"LoRa Link fetch latest mission exception: {e}")
            return None

    async def fetch_mission_detail(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Fetches full metadata and details for a specific mission."""
        url = f"{self.base_url}/missions/{mission_id}"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as e:
            logger.error(f"Failed to fetch mission {mission_id}: {e}")
            return None

    async def fetch_mission_metadata(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Fetches raw metadata.json content from /missions/{mission_id}/metadata."""
        url = f"{self.base_url}/missions/{mission_id}/metadata"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as e:
            logger.error(f"Failed to fetch mission metadata {mission_id}: {e}")
            return None

    async def get_recon_track(self) -> List[Dict[str, Any]]:
        """Returns chronologically ordered GPS flight trail and waypoints of all LoRa survey missions."""
        records = await get_all_detections(limit=100)
        lora_records = [
            r for r in records
            if r.target_type in ["LORA_MISSION", "SURVEY"] or (r.notes and "LoRa Link" in r.notes)
        ]

        if not lora_records:
            # If DB has no records yet, attempt sync once
            await self.sync_missions()
            records = await get_all_detections(limit=100)
            lora_records = [
                r for r in records
                if r.target_type in ["LORA_MISSION", "SURVEY"] or (r.notes and "LoRa Link" in r.notes)
            ]

        # Sort chronologically ascending
        lora_records.sort(key=lambda r: r.timestamp if r.timestamp else datetime.datetime.min)

        track = []
        for idx, r in enumerate(lora_records):
            mid = r.image_filename.split(".")[0] if r.image_filename else r.id
            if r.notes and "LoRa Link Mission:" in r.notes:
                try:
                    mid = r.notes.split("LoRa Link Mission:")[1].split("|")[0].strip()
                except Exception:
                    pass

            cam_name = "RunCam"
            if r.notes and "Camera:" in r.notes:
                try:
                    cam_name = r.notes.split("Camera:")[1].split("|")[0].strip()
                except Exception:
                    pass

            time_str = r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else ""
            img_name = r.image_filename or f"{mid}.jpg"

            track.append({
                "seq": idx + 1,
                "label": f"M{idx + 1}",
                "mission_id": mid,
                "completed_at": time_str,
                "lat": float(r.latitude),
                "lon": float(r.longitude),
                "altitude": float(r.altitude or 0.0),
                "image_filename": img_name,
                "image_url": f"/api/snapshots/{r.id}",
                "camera": cam_name,
                "operator": "GROUND-STATION",
                "mission_type": "SURVEY",
                "image_size": (r.lora_packets_received or 1) * 128,
                "dimensions": "1024x1024"
            })
        return track

    async def download_and_cache_image(self, mission_id: str, image_filename: Optional[str] = None) -> Optional[str]:
        """Downloads the reconstructed mission image bytes and caches locally in storage/snapshots/."""
        fname = image_filename or f"{mission_id}.jpg"
        target_path = settings.SNAPSHOT_DIR / fname

        # If already cached and non-empty, return existing path
        if target_path.exists() and target_path.stat().st_size > 0:
            return str(target_path)

        url = f"{self.base_url}/missions/{mission_id}/image"
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    with open(target_path, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"Cached LoRa Link mission image: {target_path} ({len(resp.content)} bytes)")
                    return str(target_path)
                else:
                    logger.warning(f"Could not download image for mission {mission_id}: HTTP {resp.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error downloading image for mission {mission_id}: {e}")
            return None
            if resp.status_code == 200 and resp.content:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"Cached LoRa Link mission image: {target_path} ({len(resp.content)} bytes)")
                return str(target_path)
            else:
                logger.warning(f"Could not download image for mission {mission_id}: HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error downloading image for mission {mission_id}: {e}")
            return None

    async def sync_missions(self) -> Dict[str, Any]:
        """
        Polls the LoRa Link API, detects newly completed missions,
        caches reconstructed images, saves records to Overlord DB,
        and triggers tactical dashboard alerts.
        """
        await self.check_health()
        if not self.is_online:
            return {"status": "OFFLINE", "synced": 0, "message": "LoRa Link API is not reachable"}

        missions = await self.fetch_missions(limit=50, order="desc")
        if not missions:
            return {"status": "SUCCESS", "synced": 0, "message": "No missions found on remote host"}

        # Build set of already-known mission filenames from DB
        existing_detections = await get_all_detections(limit=100)
        existing_filenames = {d.image_filename for d in existing_detections if d.image_filename}
        existing_notes = {d.notes for d in existing_detections if d.notes}

        newly_synced = 0
        for m in missions:
            mission_id = m.get("mission_id")
            if not mission_id:
                continue

            img_fname = m.get("image_filename") or f"{mission_id}.jpg"

            # Check if already processed
            if (
                mission_id in self.synced_mission_ids or
                img_fname in existing_filenames or
                any(mission_id in (n or "") for n in existing_notes)
            ):
                self.synced_mission_ids.add(mission_id)
                continue

            # Fetch full detail for this mission to extract coordinates & drone metadata
            detail = await self.fetch_mission_detail(mission_id)
            if not detail:
                continue

            meta = detail.get("metadata", {})
            loc = meta.get("location", {})
            drone_info = meta.get("drone", {})
            camera_info = meta.get("camera", {})
            mission_info = meta.get("mission", {})
            image_meta = meta.get("image", {})

            lat = float(loc.get("latitude") or settings.DEFAULT_LAT)
            lon = float(loc.get("longitude") or settings.DEFAULT_LON)
            alt = float(loc.get("altitude_m") or 0.0)
            drone_id = drone_info.get("id") or "DRONE-01"
            cam_name = camera_info.get("name") or "RunCam"
            operator = mission_info.get("operator") or "GROUND-STATION"
            raw_mission_type = mission_info.get("type") or "SURVEY"

            # Download reconstructed image
            cached_path = await self.download_and_cache_image(mission_id, img_fname)
            
            # Generate thumbnail b64 if image exists
            b64_thumb = None
            if cached_path and os.path.exists(cached_path):
                try:
                    with open(cached_path, "rb") as img_file:
                        b64_thumb = base64.b64encode(img_file.read()[:2048]).decode("ascii")
                except Exception:
                    pass

            # Calculate packet metrics
            img_size = detail.get("image_size") or 0
            packets_count = max(1, (img_size // 128) + 1)
            
            notes_str = (
                f"LoRa Link Mission: {mission_id} | "
                f"Camera: {cam_name} | "
                f"Operator: {operator} | "
                f"Resolution: {image_meta.get('width', 1024)}x{image_meta.get('height', 1024)} | "
                f"Original: {image_meta.get('original_filename', img_fname)}"
            )

            # Ingest into Overlord DB
            detection = await save_detection(
                drone_id=drone_id,
                drone_type="UAV",
                target_type="LORA_MISSION",
                confidence=0.98,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                image_filename=img_fname,
                image_path=cached_path,
                thumbnail_b64=b64_thumb,
                lora_rssi=-68.0,
                lora_snr=10.5,
                lora_packets=packets_count,
                notes=notes_str
            )

            self.synced_mission_ids.add(mission_id)
            newly_synced += 1

            ts_str = (
                detection.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                if detection.timestamp
                else time.strftime("%Y-%m-%d %H:%M:%S UTC")
            )

            # Emit real-time tactical alert over WebSocket
            await simulator.emit_alert(
                severity="TARGET_ACQUIRED",
                title=f"LORA MISSION ACQUIRED: {mission_id}",
                message=f"{drone_id} [{cam_name}] downlinked {img_fname} ({img_size} bytes) via LoRa at [{lat:.5f}°N, {lon:.5f}°E].",
                drone_id=drone_id,
                data={
                    "id": detection.id,
                    "detection_id": detection.id,
                    "mission_id": mission_id,
                    "target_type": "LORA_MISSION",
                    "lat": lat,
                    "lon": lon,
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alt,
                    "confidence": 0.98,
                    "timestamp": ts_str,
                    "image_url": f"/api/snapshots/{detection.id}",
                    "lora_rssi": -68.0,
                    "lora_snr": 10.5,
                    "lora_packets_received": packets_count,
                    "drone_id": drone_id,
                    "camera": cam_name,
                    "operator": operator,
                    "mission_type": raw_mission_type,
                    "is_lora_link": True
                }
            )

        self.last_sync_time = time.time()
        return {
            "status": "SUCCESS",
            "synced_new": newly_synced,
            "total_remote": len(missions),
            "last_sync": time.strftime("%H:%M:%S")
        }

    async def _sync_loop(self):
        """Continuous background sync loop."""
        logger.info(f"LoRa Link background sync loop started (polling every {settings.LORA_API_SYNC_INTERVAL}s)")
        while self._is_running:
            try:
                await self.sync_missions()
            except Exception as e:
                logger.debug(f"LoRa Link background sync tick: {e}")
            await asyncio.sleep(settings.LORA_API_SYNC_INTERVAL)

    def start_background_sync(self):
        if not self._is_running and settings.LORA_API_AUTO_SYNC:
            self._is_running = True
            self._background_task = asyncio.create_task(self._sync_loop())

    def stop_background_sync(self):
        self._is_running = False
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()

lora_link_service = LoRaLinkService()
