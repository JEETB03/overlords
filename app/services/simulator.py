import asyncio
import base64
import logging
import math
import random
import time
from typing import Dict, Any, List, Optional, Callable

from app.config import settings
from app.database import save_detection, get_active_geofence
from app.services.geofence_planner import is_point_in_polygon, haversine_distance_meters
from app.services.video_streamer import video_streamer
from app.services.lora_service import lora_service

logger = logging.getLogger("overlord.simulator")

class AutonomousDroneSimulator:
    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.telemetry_subscribers: List[Callable[[Dict[str, Any]], Any]] = []
        self.alert_subscribers: List[Callable[[Dict[str, Any]], Any]] = []

        # UAV State
        self.uav = {
            "drone_id": "UAV-ALPHA",
            "drone_type": "UAV",
            "lat": settings.DEFAULT_LAT,
            "lon": settings.DEFAULT_LON,
            "altitude": settings.UAV_ALTITUDE_DEFAULT,
            "heading": 45.0,
            "speed": 11.8,
            "battery": 94.0,
            "mode": "LOITER",  # "LOITER", "TRAVERSING", "RTL", "HOLD"
            "pitch": 2.1,
            "roll": -1.4,
            "satellites": 16,
            "rssi": -64.0,
            "geofence_status": "INSIDE"
        }

        # UGV State
        self.ugv = {
            "drone_id": "UGV-BRAVO",
            "drone_type": "UGV",
            "lat": settings.DEFAULT_LAT - 0.00045,
            "lon": settings.DEFAULT_LON + 0.00060,
            "altitude": 0.0,
            "heading": 135.0,
            "speed": 3.6,
            "battery": 89.0,
            "mode": "PATROL",
            "pitch": 0.5,
            "roll": 0.0,
            "satellites": 14,
            "rssi": -71.0,
            "obstacle_distance": 4.2,
            "motor_temp": 41.8,
            "geofence_status": "INSIDE"
        }

        # Active Mission Waypoints
        self.waypoints: List[Dict[str, Any]] = []
        self.current_wp_idx = 0
        self.ugv_waypoints: List[Dict[str, Any]] = []
        self.current_ugv_wp_idx = 0
        self.active_polygon: Optional[List[List[float]]] = None

        # Home location for RTL
        self.home_lat = settings.DEFAULT_LAT
        self.home_lon = settings.DEFAULT_LON

    def subscribe_telemetry(self, callback: Callable[[Dict[str, Any]], Any]):
        self.telemetry_subscribers.append(callback)

    def subscribe_alerts(self, callback: Callable[[Dict[str, Any]], Any]):
        self.alert_subscribers.append(callback)

    async def emit_alert(self, severity: str, title: str, message: str, drone_id: str, data: Optional[Dict[str, Any]] = None):
        alert_payload = {
            "type": "ALERT",
            "severity": severity,  # "INFO", "WARNING", "CRITICAL", "TARGET_ACQUIRED"
            "title": title,
            "message": message,
            "drone_id": drone_id,
            "timestamp": time.strftime("%H:%M:%S"),
            "data": data or {}
        }
        for cb in self.alert_subscribers:
            try:
                res = cb(alert_payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error emitting alert: {e}")

    def set_mission(
        self,
        polygon: List[List[float]],
        uav_waypoints: List[Dict[str, Any]],
        ugv_waypoints: Optional[List[Dict[str, Any]]] = None
    ):
        """Loads a generated traversal mission into both UAV and UGV autopilots."""
        self.active_polygon = polygon
        self.waypoints = uav_waypoints
        self.current_wp_idx = 0
        self.uav["mode"] = "TRAVERSING"
        logger.info(f"Loaded {len(uav_waypoints)} waypoints into UAV autopilot.")

        if ugv_waypoints:
            self.ugv_waypoints = ugv_waypoints
            self.current_ugv_wp_idx = 0
            self.ugv["mode"] = "TRAVERSING"
            logger.info(f"Loaded {len(ugv_waypoints)} perimeter waypoints into UGV autopilot.")

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._simulation_loop())
        logger.info("Autonomous Drone Simulator started.")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()

    async def _simulation_loop(self):
        dt = 0.2  # 5 Hz simulation update rate

        while self.is_running:
            try:
                # 1. Update UAV Dynamics
                if self.uav["mode"] == "TRAVERSING" and self.waypoints:
                    target_wp = self.waypoints[self.current_wp_idx]
                    t_lat, t_lon = target_wp["lat"], target_wp["lng"]
                    
                    # Compute vector towards waypoint
                    d_lat = t_lat - self.uav["lat"]
                    d_lon = t_lon - self.uav["lon"]
                    dist = haversine_distance_meters(self.uav["lat"], self.uav["lon"], t_lat, t_lon)

                    # Update heading smoothly
                    target_heading = math.degrees(math.atan2(d_lon, d_lat))
                    self.uav["heading"] = (self.uav["heading"] * 0.8 + target_heading * 0.2) % 360

                    # Move UAV towards target
                    step_meters = self.uav["speed"] * dt
                    if dist <= max(step_meters, 3.0):
                        # Reached waypoint -> advance to next
                        next_idx = self.current_wp_idx + 1
                        if next_idx >= len(self.waypoints):
                            # Loop interior survey grid (skipping initial transit leg)
                            next_idx = 1 if len(self.waypoints) > 1 else 0
                        self.current_wp_idx = next_idx
                    else:
                        frac = step_meters / dist
                        self.uav["lat"] += d_lat * frac
                        self.uav["lon"] += d_lon * frac

                    # Pitch/Roll dynamics during flight
                    self.uav["pitch"] = math.sin(time.time() * 2) * 2.5 + 3.0
                    self.uav["roll"] = math.cos(time.time() * 1.5) * 4.0

                elif self.uav["mode"] == "RTL":
                    # Fly towards home
                    d_lat = self.home_lat - self.uav["lat"]
                    d_lon = self.home_lon - self.uav["lon"]
                    dist = haversine_distance_meters(self.uav["lat"], self.uav["lon"], self.home_lat, self.home_lon)
                    if dist > 5.0:
                        self.uav["heading"] = math.degrees(math.atan2(d_lon, d_lat)) % 360
                        frac = (self.uav["speed"] * dt) / dist
                        self.uav["lat"] += d_lat * frac
                        self.uav["lon"] += d_lon * frac
                    else:
                        self.uav["altitude"] = max(0.0, self.uav["altitude"] - 1.5 * dt)
                        if self.uav["altitude"] <= 0.5:
                            self.uav["mode"] = "LANDED"

                else:
                    # Loiter gently around current spot
                    self.uav["lat"] += math.cos(time.time() * 0.2) * 0.000003
                    self.uav["lon"] += math.sin(time.time() * 0.2) * 0.000003
                    self.uav["heading"] = (self.uav["heading"] + 0.3) % 360
                    self.uav["pitch"] = math.sin(time.time()) * 1.0
                    self.uav["roll"] = math.cos(time.time()) * 1.0

                # Check Geofence Breach
                if self.active_polygon and len(self.active_polygon) >= 3:
                    inside = is_point_in_polygon(self.uav["lat"], self.uav["lon"], self.active_polygon)
                    new_status = "INSIDE" if inside else "BREACH"
                    if new_status != self.uav["geofence_status"]:
                        self.uav["geofence_status"] = new_status
                        if new_status == "BREACH":
                            await self.emit_alert(
                                "CRITICAL",
                                "GEOFENCE BREACH DETECTED",
                                f"UAV-ALPHA strayed outside active containment polygon! Pos: ({self.uav['lat']:.5f}, {self.uav['lon']:.5f})",
                                "UAV-ALPHA"
                            )

                # Battery drain
                self.uav["battery"] = max(5.0, self.uav["battery"] - 0.003)

                # 2. Update UGV Dynamics (Navigates to and patrols newly plotted geofence perimeter)
                if self.ugv["mode"] in ["TRAVERSING", "PATROL"] and self.ugv_waypoints:
                    target_wp = self.ugv_waypoints[self.current_ugv_wp_idx]
                    t_lat, t_lon = target_wp["lat"], target_wp["lng"]
                    d_lat = t_lat - self.ugv["lat"]
                    d_lon = t_lon - self.ugv["lon"]
                    dist = haversine_distance_meters(self.ugv["lat"], self.ugv["lon"], t_lat, t_lon)

                    target_heading = math.degrees(math.atan2(d_lon, d_lat))
                    self.ugv["heading"] = (self.ugv["heading"] * 0.75 + target_heading * 0.25) % 360

                    step_meters = self.ugv["speed"] * dt
                    if dist <= max(step_meters, 2.5):
                        # Reached perimeter waypoint
                        next_idx = self.current_ugv_wp_idx + 1
                        if next_idx >= len(self.ugv_waypoints):
                            # Loop perimeter patrol (skipping initial transit leg)
                            next_idx = 1 if len(self.ugv_waypoints) > 1 else 0
                            self.ugv["mode"] = "PATROL"
                        self.current_ugv_wp_idx = next_idx
                    else:
                        frac = step_meters / dist
                        self.ugv["lat"] += d_lat * frac
                        self.ugv["lon"] += d_lon * frac

                    self.ugv["obstacle_distance"] = 4.0 + math.sin(time.time() * 0.5) * 2.0
                    self.ugv["motor_temp"] = min(55.0, 38.0 + (self.ugv["speed"] * 1.5))
                else:
                    # Loiter gently around current spot
                    self.ugv["lat"] += math.cos(time.time() * 0.2) * 0.000001
                    self.ugv["lon"] += math.sin(time.time() * 0.2) * 0.000001

                self.ugv["battery"] = max(8.0, self.ugv["battery"] - 0.002)

                # Broadcast Telemetry
                payload = {
                    "type": "TELEMETRY",
                    "timestamp": time.time(),
                    "uav": self.uav,
                    "ugv": self.ugv
                }

                for cb in self.telemetry_subscribers:
                    try:
                        res = cb(payload)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.error(f"Error in telemetry callback: {e}")

                await asyncio.sleep(dt)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(dt)

    # Tactical Scenario Triggers
    async def trigger_life_sign_scenario(self, drone_type: str = "UAV") -> Dict[str, Any]:
        """Triggers AI detection of a living survivor (life-signs)."""
        target_type = "LIFE_SIGN / SURVIVOR"
        confidence = round(random.uniform(0.88, 0.98), 2)
        telem = self.uav if drone_type == "UAV" else self.ugv

        # Capture snapshot
        filepath, raw_bytes = video_streamer.capture_snapshot(drone_type, target_type, confidence, telem)
        b64_thumb = base64.b64encode(raw_bytes).decode("ascii")

        # Fragment into simulated LoRa packets
        tx_id, packets = lora_service.fragment_payload(raw_bytes[:1024])  # send 1KB compressed preview via LoRa
        for p in packets:
            lora_service.ingest_packet(
                transmission_id=p["transmission_id"],
                packet_num=p["packet_num"],
                total_packets=p["total_packets"],
                payload_b64=p["payload_b64"],
                rssi=p["rssi"],
                snr=p["snr"]
            )

        # Save to Database
        detection = await save_detection(
            drone_id=telem["drone_id"],
            drone_type=drone_type,
            target_type="LIFE_SIGN",
            confidence=confidence,
            latitude=telem["lat"],
            longitude=telem["lon"],
            altitude=telem.get("altitude", 0.0),
            image_filename=filepath.split("/")[-1],
            image_path=filepath,
            thumbnail_b64=b64_thumb,
            lora_rssi=lora_service.last_rssi,
            lora_snr=lora_service.last_snr,
            lora_packets=len(packets),
            notes="Thermal heat signature confirmed. Heartbeat movement patterns identified."
        )

        # Emit High Priority Tactical Alert
        await self.emit_alert(
            severity="TARGET_ACQUIRED",
            title="HUMAN LIFE-SIGN DETECTED",
            message=f"{telem['drone_id']} localized survivor thermal signature (Confidence: {int(confidence*100)}%). LoRa snapshot transmitted.",
            drone_id=telem["drone_id"],
            data={
                "detection_id": detection.id,
                "target_type": "LIFE_SIGN",
                "lat": telem["lat"],
                "lon": telem["lon"],
                "confidence": confidence,
                "image_url": f"/api/snapshots/{detection.id}"
            }
        )

        return {"detection_id": detection.id, "status": "TRIGGERED", "target": target_type}

    async def trigger_casualty_scenario(self, drone_type: str = "UAV") -> Dict[str, Any]:
        """Triggers AI detection of a casualty / deceased victim."""
        target_type = "CASUALTY / DEADBODY"
        confidence = round(random.uniform(0.85, 0.96), 2)
        telem = self.uav if drone_type == "UAV" else self.ugv

        filepath, raw_bytes = video_streamer.capture_snapshot(drone_type, target_type, confidence, telem)
        b64_thumb = base64.b64encode(raw_bytes).decode("ascii")

        tx_id, packets = lora_service.fragment_payload(raw_bytes[:1024])
        for p in packets:
            lora_service.ingest_packet(
                transmission_id=p["transmission_id"],
                packet_num=p["packet_num"],
                total_packets=p["total_packets"],
                payload_b64=p["payload_b64"],
                rssi=p["rssi"],
                snr=p["snr"]
            )

        detection = await save_detection(
            drone_id=telem["drone_id"],
            drone_type=drone_type,
            target_type="CASUALTY_DEADBODY",
            confidence=confidence,
            latitude=telem["lat"],
            longitude=telem["lon"],
            altitude=telem.get("altitude", 0.0),
            image_filename=filepath.split("/")[-1],
            image_path=filepath,
            thumbnail_b64=b64_thumb,
            lora_rssi=lora_service.last_rssi,
            lora_snr=lora_service.last_snr,
            lora_packets=len(packets),
            notes="Zero thermal differential detected. Posture corresponds to fallen casualty."
        )

        await self.emit_alert(
            severity="WARNING",
            title="CASUALTY / DEADBODY DETECTED",
            message=f"{telem['drone_id']} flagged fallen casualty at ({telem['lat']:.5f}, {telem['lon']:.5f}). Recorded in database & dispatched over LoRa.",
            drone_id=telem["drone_id"],
            data={
                "detection_id": detection.id,
                "target_type": "CASUALTY_DEADBODY",
                "lat": telem["lat"],
                "lon": telem["lon"],
                "confidence": confidence,
                "image_url": f"/api/snapshots/{detection.id}"
            }
        )

        return {"detection_id": detection.id, "status": "TRIGGERED", "target": target_type}

    async def trigger_geofence_breach_scenario(self) -> Dict[str, Any]:
        """Simulates UAV intentionally drifting outside geofence."""
        self.uav["lat"] += 0.0030
        self.uav["lon"] += 0.0035
        self.uav["geofence_status"] = "BREACH"
        await self.emit_alert(
            "CRITICAL",
            "SIMULATED GEOFENCE BREACH",
            "UAV-ALPHA exceeded containment boundary threshold by +350m! Autonomous fail-safe armed.",
            "UAV-ALPHA"
        )
        return {"status": "TRIGGERED", "mode": self.uav["mode"]}

    async def trigger_low_battery_scenario(self) -> Dict[str, Any]:
        """Simulates battery depletion failsafe."""
        self.uav["battery"] = 12.5
        self.uav["mode"] = "RTL"
        await self.emit_alert(
            "WARNING",
            "LOW BATTERY FAILSAFE (12.5%)",
            "UAV-ALPHA battery below critical threshold (15%). Autonomous Return-To-Launch (RTL) initiated!",
            "UAV-ALPHA"
        )
        return {"status": "TRIGGERED", "battery": 12.5, "mode": "RTL"}

    async def trigger_rf_jamming_scenario(self) -> Dict[str, Any]:
        """Simulates analog video interference & LoRa link degradation."""
        video_streamer.uav_noise_level = 0.85
        self.uav["rssi"] = -112.0
        lora_service.last_rssi = -118.0
        lora_service.last_snr = -4.5
        await self.emit_alert(
            "WARNING",
            "RF JAMMING & INTERFERENCE DETECTED",
            "5.8GHz video analog SNR degraded by 80%. LoRa link packet loss elevated.",
            "UAV-ALPHA"
        )
        # Restore after 10 seconds
        asyncio.get_event_loop().call_later(10.0, self._restore_rf)
        return {"status": "TRIGGERED", "noise_level": 0.85}

    def _restore_rf(self):
        video_streamer.uav_noise_level = 0.12
        self.uav["rssi"] = -64.0
        lora_service.last_rssi = -75.0
        lora_service.last_snr = 9.0

simulator = AutonomousDroneSimulator()
