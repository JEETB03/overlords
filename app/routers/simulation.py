from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.simulator import simulator

router = APIRouter(prefix="/simulation", tags=["simulation"])

class ScenarioRequest(BaseModel):
    scenario: str  # "LIFE_SIGN", "CASUALTY", "BREACH", "LOW_BATTERY", "JAMMING"
    drone_type: str = "UAV"

class DroneCommandRequest(BaseModel):
    drone_id: str
    action: str  # "ARM", "TAKEOFF", "RTL", "HOLD", "START_TRAVERSAL"
    params: Optional[Dict[str, Any]] = None

@router.post("/trigger")
async def trigger_scenario(req: ScenarioRequest):
    """Triggers real-time operational scenarios to test tactical responses."""
    sc = req.scenario.upper()
    if sc == "LIFE_SIGN":
        res = await simulator.trigger_life_sign_scenario(req.drone_type)
    elif sc == "CASUALTY":
        res = await simulator.trigger_casualty_scenario(req.drone_type)
    elif sc == "BREACH":
        res = await simulator.trigger_geofence_breach_scenario()
    elif sc == "LOW_BATTERY":
        res = await simulator.trigger_low_battery_scenario()
    elif sc == "JAMMING":
        res = await simulator.trigger_rf_jamming_scenario()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    return res

@router.post("/command")
async def send_drone_command(cmd: DroneCommandRequest):
    """Dispatches tactical control commands to UAV or UGV."""
    act = cmd.action.upper()
    drone = simulator.uav if "UAV" in cmd.drone_id else simulator.ugv
    
    if act == "RTL":
        drone["mode"] = "RTL"
        await simulator.emit_alert("WARNING", "RTL COMMAND ISSUED", f"{cmd.drone_id} returning to launch coordinates.", cmd.drone_id)
    elif act == "HOLD":
        drone["mode"] = "HOLD"
        drone["speed"] = 0.0
        await simulator.emit_alert("INFO", "POSITION HOLD ENGAGED", f"{cmd.drone_id} holding current position.", cmd.drone_id)
    elif act == "START_TRAVERSAL":
        if simulator.waypoints:
            drone["mode"] = "TRAVERSING"
            drone["speed"] = 12.0
            await simulator.emit_alert("INFO", "MISSION TRAVERSAL STARTED", f"{cmd.drone_id} initiated boustrophedon sweep.", cmd.drone_id)
        else:
            raise HTTPException(status_code=400, detail="No active traversal waypoints loaded. Generate a geofence first.")
    elif act == "TAKEOFF":
        drone["altitude"] = 65.0
        drone["mode"] = "LOITER"
        await simulator.emit_alert("INFO", "TAKEOFF COMPLETED", f"{cmd.drone_id} reached 65m AGL altitude.", cmd.drone_id)
    else:
        drone["mode"] = act

    return {"status": "ACKNOWLEDGED", "drone_id": cmd.drone_id, "mode": drone["mode"]}
