import asyncio
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.video_streamer import video_streamer
from app.services.simulator import simulator

router = APIRouter(prefix="/stream", tags=["video"])

class NoiseSettings(BaseModel):
    drone_type: str  # "UAV" or "UGV"
    noise_level: float  # 0.0 to 1.0

async def mjpeg_frame_generator(drone_type: str):
    """Generates continuous MJPEG multipart stream."""
    delay = 1.0 / 25.0  # 25 FPS
    while True:
        try:
            telem = simulator.uav if drone_type == "UAV" else simulator.ugv
            frame_bytes = video_streamer.render_frame(drone_type, telem)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.1)

@router.get("/uav")
async def stream_uav_video():
    """Live analog video feed with HUD from UAV."""
    return StreamingResponse(
        mjpeg_frame_generator("UAV"),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get("/ugv")
async def stream_ugv_video():
    """Live analog video feed with HUD from UGV Ground Rover."""
    return StreamingResponse(
        mjpeg_frame_generator("UGV"),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/noise")
async def set_analog_noise(settings: NoiseSettings):
    """Adjusts analog RF noise / jamming intensity."""
    if settings.drone_type == "UAV":
        video_streamer.uav_noise_level = max(0.0, min(1.0, settings.noise_level))
    else:
        video_streamer.ugv_noise_level = max(0.0, min(1.0, settings.noise_level))
    return {"status": "SUCCESS", "drone_type": settings.drone_type, "noise_level": settings.noise_level}

@router.post("/toggle-thermal")
async def toggle_thermal_mode():
    """Toggles UAV FLIR thermal palette."""
    video_streamer.uav_flir_thermal = not video_streamer.uav_flir_thermal
    return {"status": "SUCCESS", "uav_flir_thermal": video_streamer.uav_flir_thermal}
