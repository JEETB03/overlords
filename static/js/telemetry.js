/**
 * OVERLORD TELEMETRY & AUDIO ALERT SUBSYSTEM
 * Handles live WebSockets, HUD gauge updates, and tactical sound cues via Web Audio API.
 */

class TelemetryManager {
  constructor() {
    this.ws = null;
    this.audioCtx = null;
    this.audioEnabled = true;
    this.reconnectTimer = null;
  }

  init() {
    this.initAudioContext();
    this.connectWebSocket();
  }

  initAudioContext() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      this.audioCtx = new AudioContext();
    } catch (e) {
      console.warn("Web Audio API not supported:", e);
    }
  }

  playTacticalSound(type) {
    if (!this.audioEnabled || !this.audioCtx) return;
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }

    const now = this.audioCtx.currentTime;
    const osc = this.audioCtx.createOscillator();
    const gain = this.audioCtx.createGain();
    osc.connect(gain);
    gain.connect(this.audioCtx.destination);

    if (type === "TARGET_ACQUIRED") {
      // High-tech two-tone positive chime
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(1320, now + 0.15);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else if (type === "CRITICAL") {
      // Rapid warble alert
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(950, now);
      osc.frequency.setValueAtTime(650, now + 0.1);
      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === "WARNING") {
      // Amber caution beep
      osc.type = "triangle";
      osc.frequency.setValueAtTime(580, now);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
      osc.start(now);
      osc.stop(now + 0.2);
    } else {
      // Standard UI blip
      osc.type = "sine";
      osc.frequency.setValueAtTime(1200, now);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
      osc.start(now);
      osc.stop(now + 0.08);
    }
  }

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/telemetry/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("Telemetry WebSocket connected.");
      document.getElementById('ws-status-dot').className = "status-dot pulse";
      document.getElementById('ws-status-text').innerText = "LIVE (5 Hz)";
      if (this.reconnectTimer) clearInterval(this.reconnectTimer);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "TELEMETRY") {
          this.handleTelemetryUpdate(msg);
        } else if (msg.type === "ALERT") {
          this.handleAlertEvent(msg);
        } else if (msg.type === "INITIAL_STATE") {
          if (msg.uav) this.updateUAVHUD(msg.uav);
          if (msg.ugv) this.updateUGVHUD(msg.ugv);
        }
      } catch (err) {
        console.error("WS Parse error:", err);
      }
    };

    this.ws.onclose = () => {
      document.getElementById('ws-status-dot').className = "status-dot red";
      document.getElementById('ws-status-text').innerText = "DISCONNECTED";
      // Auto-reconnect after 2 seconds
      setTimeout(() => this.connectWebSocket(), 2000);
    };
  }

  handleTelemetryUpdate(data) {
    const uav = data.uav;
    const ugv = data.ugv;

    if (uav) this.updateUAVHUD(uav);
    if (ugv) this.updateUGVHUD(ugv);

    if (window.tacticalMap) {
      window.tacticalMap.updatePositions(uav, ugv);
    }
  }

  updateUAVHUD(uav) {
    document.getElementById('uav-alt-val').innerText = `${Math.round(uav.altitude || 0)}m`;
    document.getElementById('uav-speed-val').innerText = `${(uav.speed || 0).toFixed(1)} m/s`;
    document.getElementById('uav-hdg-val').innerText = `${Math.round(uav.heading || 0)}°`;
    document.getElementById('uav-mode-badge').innerText = uav.mode || "AUTO";
    document.getElementById('uav-batt-val').innerText = `${(uav.battery || 0).toFixed(1)}%`;
    document.getElementById('uav-batt-bar').style.width = `${Math.max(0, Math.min(100, uav.battery || 0))}%`;
    document.getElementById('uav-sats-val').innerText = uav.satellites || 16;
    document.getElementById('uav-rssi-val').innerText = `${Math.round(uav.rssi || -65)} dBm`;

    // Geofence status pill in header
    const gfPill = document.getElementById('geofence-status-pill');
    if (gfPill) {
      if (uav.geofence_status === "BREACH") {
        gfPill.className = "status-pill red";
        gfPill.innerHTML = '<span class="status-dot red pulse"></span> GEOFENCE BREACH';
      } else {
        gfPill.className = "status-pill";
        gfPill.innerHTML = '<span class="status-dot"></span> GEOFENCE: CONTAINED';
      }
    }
  }

  updateUGVHUD(ugv) {
    document.getElementById('ugv-speed-val').innerText = `${(ugv.speed || 0).toFixed(1)} km/h`;
    document.getElementById('ugv-obs-val').innerText = `${(ugv.obstacle_distance || 0).toFixed(1)}m`;
    document.getElementById('ugv-temp-val').innerText = `${Math.round(ugv.motor_temp || 42)}°C`;
    document.getElementById('ugv-mode-badge').innerText = ugv.mode || "PATROL";
    document.getElementById('ugv-batt-val').innerText = `${(ugv.battery || 0).toFixed(1)}%`;
    document.getElementById('ugv-batt-bar').style.width = `${Math.max(0, Math.min(100, ugv.battery || 0))}%`;
    document.getElementById('ugv-hdg-val').innerText = `${Math.round(ugv.heading || 0)}°`;
  }

  handleAlertEvent(alert) {
    this.playTacticalSound(alert.severity);

    // Add to bottom alert feed console
    const feed = document.getElementById('tactical-alerts-feed');
    if (feed) {
      const item = document.createElement('div');
      item.className = `alert-item ${alert.severity}`;
      item.innerHTML = `
        <span style="color: #6a82a9;">[${alert.timestamp}]</span>
        <strong style="letter-spacing: 0.5px;">${alert.title}</strong>
        <span>- ${alert.message}</span>
      `;
      feed.insertBefore(item, feed.firstChild);
      if (feed.children.length > 25) {
        feed.removeChild(feed.lastChild);
      }
    }

    // If target acquired, place map marker & refresh snapshot gallery
    if (alert.severity === "TARGET_ACQUIRED" || alert.severity === "WARNING") {
      if (alert.data && alert.data.lat && alert.data.lon && window.tacticalMap) {
        window.tacticalMap.addDetectionMarker(alert.data);
      }
      if (window.detectionManager) {
        window.detectionManager.fetchDetections();
      }
    }
  }
}
