import asyncio
import datetime
import json
import logging
import urllib.request
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, desc

from app.config import settings
from app.models import Base, DetectionModel, GeofenceModel, TelemetryLogModel

logger = logging.getLogger("overlord.db")

# Detect engine dialect
db_url = settings.DATABASE_URL
active_db_types = []
if "postgres" in db_url:
    active_db_types.append("PostgreSQL")
else:
    active_db_types.append("SQLite")

if settings.CLICKHOUSE_URL:
    active_db_types.append("ClickHouse")

active_db_type = " + ".join(active_db_types)

# Create async engine
engine = create_async_engine(
    db_url,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def _init_clickhouse_sync(url: str):
    """Initializes ClickHouse schema for detection and snapshot storage."""
    try:
        create_sql = """
        CREATE TABLE IF NOT EXISTS detections (
            id String,
            timestamp DateTime64(3, 'UTC'),
            drone_id String,
            drone_type String,
            target_type String,
            confidence Float32,
            latitude Float64,
            longitude Float64,
            altitude Float32,
            image_filename String,
            image_path String,
            lora_rssi Float32,
            lora_snr Float32,
            lora_packets_received UInt32,
            status String,
            notes String
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, id);
        """
        req = urllib.request.Request(
            f"{url.rstrip('/')}/",
            data=create_sql.encode('utf-8'),
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            logger.info(f"ClickHouse schema verified/created at {url}")
    except Exception as e:
        logger.warning(f"ClickHouse table initialization notice: {e}")

def _send_clickhouse_insert_sync(url: str, data: Dict[str, Any]):
    """Inserts a detection row into ClickHouse via JSONEachRow HTTP endpoint."""
    try:
        payload = json.dumps(data)
        req = urllib.request.Request(
            f"{url.rstrip('/')}/?query=INSERT+INTO+detections+FORMAT+JSONEachRow",
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            pass
        logger.info(f"Detection {data.get('id')} persisted into ClickHouse at {url}")
    except Exception as e:
        logger.warning(f"ClickHouse ingestion note: {e}")

async def save_detection_to_clickhouse(data: Dict[str, Any]):
    """Asynchronously dispatches detection record to ClickHouse."""
    if not settings.CLICKHOUSE_URL:
        return
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_clickhouse_insert_sync, settings.CLICKHOUSE_URL, data)
    except Exception as e:
        logger.debug(f"ClickHouse async dispatch: {e}")

async def init_db():
    """Initializes the database schema for PostgreSQL/SQLite and ClickHouse."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Primary database initialized successfully using [{active_db_type}] at {db_url}")
    except Exception as e:
        logger.error(f"Failed to initialize database with {db_url}: {e}")
        # Fallback to local SQLite if PostgreSQL connection fails
        if "postgres" in db_url:
            logger.warning("Attempting automatic fallback to SQLite...")
            sqlite_url = f"sqlite+aiosqlite:///{settings.SNAPSHOT_DIR.parent / 'overlord_fallback.db'}"
            fallback_engine = create_async_engine(sqlite_url, echo=False)
            async with fallback_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info(f"Fallback SQLite database initialized at {sqlite_url}")

    # ClickHouse initialization if configured
    if settings.CLICKHOUSE_URL:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _init_clickhouse_sync, settings.CLICKHOUSE_URL)
        except Exception as e:
            logger.warning(f"ClickHouse async init note: {e}")

async def get_db():
    """Dependency for obtaining async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Database Helper Functions
async def save_detection(
    drone_id: str,
    drone_type: str,
    target_type: str,
    confidence: float,
    latitude: float,
    longitude: float,
    altitude: float = 0.0,
    image_filename: Optional[str] = None,
    image_path: Optional[str] = None,
    thumbnail_b64: Optional[str] = None,
    lora_rssi: float = -75.0,
    lora_snr: float = 8.5,
    lora_packets: int = 1,
    notes: Optional[str] = ""
) -> DetectionModel:
    async with AsyncSessionLocal() as session:
        detection = DetectionModel(
            drone_id=drone_id,
            drone_type=drone_type,
            target_type=target_type,
            confidence=confidence,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            image_filename=image_filename,
            image_path=image_path,
            thumbnail_b64=thumbnail_b64,
            lora_rssi=lora_rssi,
            lora_snr=lora_snr,
            lora_packets_received=lora_packets,
            notes=notes
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Concurrently archive snapshot metadata into ClickHouse if configured
    if settings.CLICKHOUSE_URL:
        ts_ch = detection.timestamp.strftime("%Y-%m-%d %H:%M:%S") if detection.timestamp else datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        asyncio.create_task(save_detection_to_clickhouse({
            "id": detection.id,
            "timestamp": ts_ch,
            "drone_id": drone_id,
            "drone_type": drone_type,
            "target_type": target_type,
            "confidence": float(confidence),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "altitude": float(altitude),
            "image_filename": image_filename or "",
            "image_path": image_path or "",
            "lora_rssi": float(lora_rssi),
            "lora_snr": float(lora_snr),
            "lora_packets_received": int(lora_packets),
            "status": detection.status,
            "notes": notes or ""
        }))

    return detection

async def get_all_detections(limit: int = 50) -> List[DetectionModel]:
    async with AsyncSessionLocal() as session:
        stmt = select(DetectionModel).order_by(desc(DetectionModel.timestamp)).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_detection_by_id(detection_id: str) -> Optional[DetectionModel]:
    async with AsyncSessionLocal() as session:
        stmt = select(DetectionModel).where(DetectionModel.id == detection_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

async def update_detection_status(detection_id: str, status: str, notes: Optional[str] = None) -> Optional[DetectionModel]:
    async with AsyncSessionLocal() as session:
        stmt = select(DetectionModel).where(DetectionModel.id == detection_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.status = status
            if notes:
                record.notes = notes
            await session.commit()
            await session.refresh(record)
        return record

async def save_geofence(
    name: str,
    polygon_coords: List[List[float]],
    traversal_path: List[Dict[str, Any]],
    area_sqm: float,
    duration_sec: float
) -> GeofenceModel:
    async with AsyncSessionLocal() as session:
        # Mark other geofences inactive
        await session.execute(update(GeofenceModel).values(is_active=False))
        
        geofence = GeofenceModel(
            name=name,
            polygon_geojson=json.dumps(polygon_coords),
            traversal_path_geojson=json.dumps(traversal_path),
            area_sqm=area_sqm,
            estimated_duration_sec=duration_sec,
            is_active=True
        )
        session.add(geofence)
        await session.commit()
        await session.refresh(geofence)
        return geofence

async def get_active_geofence() -> Optional[GeofenceModel]:
    async with AsyncSessionLocal() as session:
        stmt = select(GeofenceModel).where(GeofenceModel.is_active == True).order_by(desc(GeofenceModel.created_at)).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
