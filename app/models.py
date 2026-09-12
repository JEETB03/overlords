import datetime
import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# SQLAlchemy ORM Models
class DetectionModel(Base):
    __tablename__ = "detections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    drone_id = Column(String(32), index=True)
    drone_type = Column(String(16))  # "UAV" or "UGV"
    target_type = Column(String(32), index=True)  # "LIFE_SIGN", "CASUALTY_DEADBODY", etc.
    confidence = Column(Float, default=0.0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, default=0.0)
    image_filename = Column(String(255), nullable=True)
    image_path = Column(String(512), nullable=True)
    thumbnail_b64 = Column(Text, nullable=True)
    lora_rssi = Column(Float, default=-75.0)
    lora_snr = Column(Float, default=8.5)
    lora_packets_received = Column(Integer, default=1)
    status = Column(String(32), default="UNCONFIRMED")  # "UNCONFIRMED", "VERIFIED", "DISPATCHED"
    notes = Column(Text, nullable=True)

class GeofenceModel(Base):
    __tablename__ = "geofences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), default="Geofence Mission Alpha")
    polygon_geojson = Column(Text, nullable=False)  # JSON string of coordinates [[lat, lon], ...]
    traversal_path_geojson = Column(Text, nullable=True)  # JSON list of waypoints
    area_sqm = Column(Float, default=0.0)
    estimated_duration_sec = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TelemetryLogModel(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    drone_id = Column(String(32), index=True)
    drone_type = Column(String(16))
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    heading = Column(Float)
    speed = Column(Float)
    battery = Column(Float)
    mode = Column(String(32))
    pitch = Column(Float, default=0.0)
    roll = Column(Float, default=0.0)
    satellites = Column(Integer, default=14)
    rssi = Column(Float, default=-65.0)

# Pydantic Schemas for API
class Coordinate(BaseModel):
    lat: float
    lng: float

class TelemetryData(BaseModel):
    drone_id: str
    drone_type: str  # "UAV" or "UGV"
    lat: float
    lon: float
    altitude: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    battery: float = 100.0
    mode: str = "AUTO"
    pitch: float = 0.0
    roll: float = 0.0
    satellites: int = 14
    rssi: float = -65.0
    obstacle_distance: Optional[float] = None  # for UGV
    motor_temp: Optional[float] = None        # for UGV
    geofence_status: str = "INSIDE"           # "INSIDE", "BREACH", "NO_GEOFENCE"
    timestamp: Optional[str] = None

class DetectionCreate(BaseModel):
    drone_id: str
    drone_type: str
    target_type: str  # "LIFE_SIGN", "CASUALTY_DEADBODY", etc.
    confidence: float
    lat: float
    lon: float
    altitude: float = 0.0
    image_b64: Optional[str] = None
    lora_rssi: float = -75.0
    lora_snr: float = 9.0
    notes: Optional[str] = ""

class DetectionOut(BaseModel):
    id: str
    timestamp: str
    drone_id: str
    drone_type: str
    target_type: str
    confidence: float
    lat: float
    lon: float
    altitude: float
    image_url: Optional[str]
    thumbnail_b64: Optional[str]
    lora_rssi: float
    lora_snr: float
    lora_packets_received: int
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True

class GeofenceCreate(BaseModel):
    name: str = "Zone Alpha"
    polygon: List[List[float]]  # list of [lat, lng]
    lane_spacing_meters: float = 25.0
    altitude_meters: float = 65.0
    heading_angle_deg: float = 0.0

class TraversalWaypoint(BaseModel):
    id: int
    lat: float
    lng: float
    alt: float
    action: str = "WAYPOINT"  # "TAKEOFF", "WAYPOINT", "RTL", "LOITER"

class GeofenceResponse(BaseModel):
    id: str
    name: str
    polygon: List[List[float]]
    traversal_path: List[TraversalWaypoint]
    area_sqm: float
    estimated_duration_sec: float
    is_active: bool
    created_at: str

class LoRaPacketIn(BaseModel):
    device_id: str
    packet_id: int
    total_packets: int
    payload_chunk_b64: str
    rssi: float = -80.0
    snr: float = 8.0
    crc_valid: bool = True
    freq_mhz: float = 868.1

class DroneCommand(BaseModel):
    action: str  # "ARM", "DISARM", "TAKEOFF", "RTL", "START_TRAVERSAL", "HOLD"
    params: Optional[Dict[str, Any]] = None
