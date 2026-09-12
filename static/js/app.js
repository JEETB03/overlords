/**
 * OVERLORD APPLICATION ROOT CONTROLLER
 * Bootstraps subsystems and binds all UI and simulation events.
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize Subsystems
  const defaultLat = window.OVERLORD_CONFIG ? window.OVERLORD_CONFIG.defaultLat : 28.613939;
  const defaultLon = window.OVERLORD_CONFIG ? window.OVERLORD_CONFIG.defaultLon : 77.209021;

  window.tacticalMap = new TacticalMap('tactical-map', defaultLat, defaultLon);
  window.tacticalMap.init();

  window.telemetryManager = new TelemetryManager();
  window.telemetryManager.init();

  window.detectionManager = new DetectionManager();
  window.detectionManager.init();

  // 2. Setup Clock
  setInterval(updateMissionClock, 1000);
  updateMissionClock();

  // 3. Bind Geofence Drawing Controls
  const btnDraw = document.getElementById('btn-draw-geofence');
  if (btnDraw) {
    btnDraw.addEventListener('click', () => {
      window.tacticalMap.startDrawingGeofence();
    });
  }

  const btnFinish = document.getElementById('btn-finish-geofence');
  if (btnFinish) {
    btnFinish.addEventListener('click', () => {
      window.tacticalMap.finishDrawingGeofence();
    });
  }

  const btnGenPath = document.getElementById('btn-gen-path');
  if (btnGenPath) {
    btnGenPath.addEventListener('click', () => {
      window.tacticalMap.generateTraversalPath();
    });
  }

  const btnDeploy = document.getElementById('btn-deploy-mission');
  if (btnDeploy) {
    btnDeploy.addEventListener('click', () => {
      window.tacticalMap.deployMissionToDrone();
    });
  }

  // 4. Bind Scenario Simulation Buttons
  bindScenarioButton('sim-btn-life-sign', 'LIFE_SIGN');
  bindScenarioButton('sim-btn-casualty', 'CASUALTY');
  bindScenarioButton('sim-btn-breach', 'BREACH');
  bindScenarioButton('sim-btn-low-battery', 'LOW_BATTERY');
  bindScenarioButton('sim-btn-jamming', 'JAMMING');

  const btnLoraBurst = document.getElementById('sim-btn-lora-burst');
  if (btnLoraBurst) {
    btnLoraBurst.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/lora/test-burst', { method: 'POST' });
        const data = await res.json();
        console.log("LoRa burst:", data);
      } catch (e) {
        console.error(e);
      }
    });
  }

  // 5. Bind Drone C2 Commands
  const btnRTL = document.getElementById('btn-uav-rtl');
  if (btnRTL) {
    btnRTL.addEventListener('click', () => sendDroneCommand('UAV-ALPHA', 'RTL'));
  }

  const btnHold = document.getElementById('btn-uav-hold');
  if (btnHold) {
    btnHold.addEventListener('click', () => sendDroneCommand('UAV-ALPHA', 'HOLD'));
  }

  const btnTakeoff = document.getElementById('btn-uav-takeoff');
  if (btnTakeoff) {
    btnTakeoff.addEventListener('click', () => sendDroneCommand('UAV-ALPHA', 'TAKEOFF'));
  }

  // 6. Video Stream Controls
  const uavNoiseSlider = document.getElementById('uav-noise-slider');
  if (uavNoiseSlider) {
    uavNoiseSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      fetch('/api/stream/noise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drone_type: 'UAV', noise_level: val })
      });
    });
  }

  const btnThermal = document.getElementById('btn-toggle-thermal');
  if (btnThermal) {
    btnThermal.addEventListener('click', () => {
      fetch('/api/stream/toggle-thermal', { method: 'POST' });
    });
  }

  // 7. Modal Controls
  const modalClose = document.getElementById('modal-btn-close');
  if (modalClose) {
    modalClose.addEventListener('click', () => window.detectionManager.closeModal());
  }

  const modalVerify = document.getElementById('modal-btn-verify');
  if (modalVerify) {
    modalVerify.addEventListener('click', () => window.detectionManager.verifyTarget());
  }

  const modalEvac = document.getElementById('modal-btn-evac');
  if (modalEvac) {
    modalEvac.addEventListener('click', () => window.detectionManager.dispatchEvac());
  }

  // 8. Audio Toggle
  const btnAudio = document.getElementById('btn-toggle-audio');
  if (btnAudio) {
    btnAudio.addEventListener('click', () => {
      window.telemetryManager.audioEnabled = !window.telemetryManager.audioEnabled;
      btnAudio.innerText = window.telemetryManager.audioEnabled ? "AUDIO: ON" : "AUDIO: OFF";
      btnAudio.classList.toggle('btn-amber', !window.telemetryManager.audioEnabled);
    });
  }
});

function bindScenarioButton(elementId, scenarioName) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.addEventListener('click', async () => {
    try {
      await fetch('/api/simulation/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioName, drone_type: 'UAV' })
      });
    } catch (e) {
      console.error(`Failed to trigger ${scenarioName}:`, e);
    }
  });
}

async function sendDroneCommand(droneId, action) {
  try {
    await fetch('/api/simulation/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drone_id: droneId, action: action })
    });
  } catch (e) {
    console.error(`Failed to send ${action} to ${droneId}:`, e);
  }
}

function updateMissionClock() {
  const now = new Date();
  const utcStr = now.toISOString().substring(11, 19) + " UTC";
  const clockEl = document.getElementById('mission-clock');
  if (clockEl) {
    clockEl.innerText = utcStr;
  }
}
