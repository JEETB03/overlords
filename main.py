import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse

from app.config import settings
from app.database import init_db, active_db_type, get_detection_by_id
from app.services.simulator import simulator
from app.services.lora_link_service import lora_link_service
from app.routers import telemetry, video, geofence, detections, lora, simulation, lora_link

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await simulator.start()
    lora_link_service.start_background_sync()
    yield
    # Shutdown
    lora_link_service.stop_background_sync()
    await simulator.stop()

TAGS_METADATA = [
    {
        "name": "system",
        "description": "System health diagnostics, database engine status, and operational readiness."
    },
    {
        "name": "lora-link",
        "description": "Hardware LoRa Link Mission Data API integration (`http://172.16.59.210:8000`). Discovers and reassembles downlinked drone survey missions, camera metadata (RunCam), GPS flight tracks, and reconstructed high-resolution aerial imagery."
    },
    {
        "name": "telemetry",
        "description": "Real-time bi-directional WebSocket (5Hz) and REST telemetry for autonomous UAV and UGV fleet coordinates, attitudes, battery, and alerts."
    },
    {
        "name": "video",
        "description": "Live analog video feeds (5.8 GHz UAV FLIR IR thermal & UGV rover optical) with tactical OSD HUD, CRT scanlines, and RF static noise simulation."
    },
    {
        "name": "geofence",
        "description": "Tactical polygon geofencing, computational boustrophedon (lawnmower) path generation, flight time estimation, and autopilot mission dispatch."
    },
    {
        "name": "detections",
        "description": "AI computer vision target detection log, target classification (Survivors, Casualties), and snapshot image management."
    },
    {
        "name": "lora",
        "description": "LoRa 868/915 MHz low-bandwidth radio protocol simulation, chunked packet fragmentation/reassembly, and transceiver hardware gateway."
    },
    {
        "name": "simulation",
        "description": "Scenario injection controls (Life-Sign, Casualty, Geofence Breach, Low Battery RTL) and drone flight mode commands."
    }
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    summary="Tactical Autonomous Fleet C2 & LoRa Link Mission Integration Engine",
    description="""
## OVERLORD // Autonomous UAV & UGV Tactical Command & Control (C2) Dashboard

OVERLORD provides mission-critical command, control, communications, computers, intelligence, surveillance, and reconnaissance (C4ISR) capabilities for autonomous drone fleets.

### Key Capabilities & Subsystems
* **Dual Live Analog Video Streams**: Live UAV thermal FLIR and UGV rover optical streams with tactical OSD overlays.
* **Autonomous Lawnmower Geofence Planner**: Interactive polygon survey generation with computational boustrophedon waypoints.
* **Physical LoRa Link Station Integration**: Real-time synchronization with ground station RX hardware (`http://172.16.59.210:8000`) for receiving aerial reconnaissance missions, RunCam imagery, and GPS flight corridors.
* **AI Target Detections**: High-resolution image capture with classified life-signs and casualties.
* **Real-time Tactical Telemetry**: Low-latency 5Hz WebSocket bus for fleet status, battery health, and alarm dispatch.
""",
    version="1.1.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include Routers
app.include_router(telemetry.router, prefix=settings.API_PREFIX)
app.include_router(video.router, prefix=settings.API_PREFIX)
app.include_router(geofence.router, prefix=settings.API_PREFIX)
app.include_router(detections.router, prefix=settings.API_PREFIX)
app.include_router(lora.router, prefix=settings.API_PREFIX)
app.include_router(simulation.router, prefix=settings.API_PREFIX)
app.include_router(lora_link.router, prefix=settings.API_PREFIX)

@app.get("/", response_class=HTMLResponse)
async def dashboard_index(request: Request):
    """Renders the main Tactical Command & Control Dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "db_type": active_db_type,
            "lora_freq": settings.LORA_FREQUENCY_MHZ,
            "lora_api_url": settings.LORA_API_BASE_URL,
            "default_lat": settings.DEFAULT_LAT,
            "default_lon": settings.DEFAULT_LON
        }
    )

@app.get("/api/snapshots/{detection_id}")
async def serve_snapshot_image(detection_id: str):
    """Serves high-resolution snapshot image corresponding to a detection or mission."""
    record = await get_detection_by_id(detection_id)
    if record and record.image_path and os.path.exists(record.image_path):
        return FileResponse(record.image_path, media_type="image/jpeg")

    # Direct filename / mission_id lookup
    for ext in ["", ".jpg", ".jpeg", ".png"]:
        candidate = settings.SNAPSHOT_DIR / f"{detection_id}{ext}"
        if candidate.exists() and candidate.stat().st_size > 0:
            return FileResponse(str(candidate), media_type="image/jpeg")

    # If it's a LoRa Link mission ID, attempt on-demand retrieval
    if detection_id.startswith("LL-"):
        cached = await lora_link_service.download_and_cache_image(detection_id)
        if cached and os.path.exists(cached):
            return FileResponse(cached, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Snapshot not found")

@app.get("/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "db_type": active_db_type,
        "uav_mode": simulator.uav.get("mode"),
        "ugv_mode": simulator.ugv.get("mode"),
        "lora_active": settings.LORA_ENABLED
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
