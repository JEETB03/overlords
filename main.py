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
from app.routers import telemetry, video, geofence, detections, lora, simulation

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await simulator.start()
    yield
    # Shutdown
    await simulator.stop()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
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
            "default_lat": settings.DEFAULT_LAT,
            "default_lon": settings.DEFAULT_LON
        }
    )

@app.get("/api/snapshots/{detection_id}")
async def serve_snapshot_image(detection_id: str):
    """Serves high-resolution snapshot image corresponding to a detection."""
    record = await get_detection_by_id(detection_id)
    if not record or not record.image_path:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if not os.path.exists(record.image_path):
        raise HTTPException(status_code=404, detail="Image file missing from disk")
    return FileResponse(record.image_path, media_type="image/jpeg")

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
