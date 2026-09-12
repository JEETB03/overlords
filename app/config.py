from pydantic_settings import BaseSettings
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
SNAPSHOTS_DIR = STORAGE_DIR / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "OVERLORD Tactical C2 System"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database Settings
    # Supports PostgreSQL (e.g. postgresql+asyncpg://user:pass@localhost:5432/overlord)
    # Default falls back to SQLite
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite+aiosqlite:///{STORAGE_DIR / 'overlord.db'}"
    )
    # ClickHouse optional endpoint (e.g. http://localhost:8123)
    CLICKHOUSE_URL: str = os.getenv("CLICKHOUSE_URL", "")
    
    # Storage
    SNAPSHOT_DIR: Path = SNAPSHOTS_DIR
    
    # LoRa Module Settings
    LORA_ENABLED: bool = True
    LORA_FREQUENCY_MHZ: float = 868.100  # or 915.000 MHz
    LORA_BANDWIDTH_KHZ: float = 125.0
    LORA_SPREADING_FACTOR: int = 7       # SF7 - SF12
    LORA_CODING_RATE: str = "4/5"
    LORA_SERIAL_PORT: str = os.getenv("LORA_SERIAL_PORT", "/dev/ttyUSB0")
    LORA_BAUD_RATE: int = 115200
    LORA_SIMULATION_MODE: bool = True    # Auto-fallback to simulation if no hardware port
    
    # Drones Initial Reference Coordinates (Tactical Command Zone)
    DEFAULT_LAT: float = 28.613939
    DEFAULT_LON: float = 77.209021
    UAV_ALTITUDE_DEFAULT: float = 65.0   # meters AGL
    
    # Video Feeds
    VIDEO_FPS: int = 25
    VIDEO_WIDTH: int = 640
    VIDEO_HEIGHT: int = 480
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
