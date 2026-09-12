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

    // 1. Add to bottom alert feed console
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

    // 2. Check if this is an AI target detection (Life-Sign or Casualty)
    const isDetection = (
      alert.severity === "TARGET_ACQUIRED" ||
      (alert.data && (alert.data.target_type || alert.data.id || alert.data.detection_id)) ||
      (alert.title && (alert.title.includes("DETECTED") || alert.title.includes("LIFE") || alert.title.includes("CASUALTY")))
    );

    if (isDetection && alert.data) {
      // Pop up on map with marker, centering, and open popup
      if (window.tacticalMap && alert.data.lat && alert.data.lon) {
        window.tacticalMap.addDetectionMarker(alert.data, true);
      }

      // Pop up on alerts (interactive tactical toast on dashboard UI)
      this.showDetectionAlertToast(alert);

      // Refresh snapshot gallery stream
      if (window.detectionManager) {
        window.detectionManager.fetchDetections();
      }
    }
  }

  showDetectionAlertToast(alert) {
    const container = document.getElementById('alert-toast-container');
    if (!container) return;

    const d = alert.data || {};
    const detId = d.id || d.detection_id || ('det_' + Date.now());
    const isLifeSign = (
      (alert.title && alert.title.includes("LIFE")) ||
      (d.target_type && d.target_type.toUpperCase().includes("LIFE")) ||
      (d.target_type && d.target_type.toUpperCase().includes("SURVIVOR"))
    );

    const badgeText = isLifeSign ? "SURVIVOR (LIFE-SIGN)" : "CASUALTY (DEADBODY)";
    const lat = Number(d.latitude || d.lat || 0);
    const lon = Number(d.longitude || d.lon || 0);
    const timeStr = d.timestamp || alert.timestamp || (new Date().toISOString().replace('T', ' ').substring(0, 19) + " UTC");
    const confPct = Math.round(Number(d.confidence || 0.92) * 100);
    const imgUrl = d.image_url || `/api/snapshots/${detId}`;
    const droneId = d.drone_id || alert.drone_id || "UAV-ALPHA";
    const loraRssi = (d.lora_rssi !== undefined && d.lora_rssi !== null) ? `${Number(d.lora_rssi).toFixed(1)} dBm` : "-72.0 dBm";

    const toast = document.createElement('div');
    toast.className = `detection-toast ${isLifeSign ? 'toast-life' : 'toast-casualty'}`;
    toast.id = `toast-${detId}`;

    toast.innerHTML = `
      <div class="toast-side-indicator"></div>
      <div class="toast-inner">
        <div class="toast-top-row">
          <div class="toast-tag-group">
            <span class="toast-pulse-dot"></span>
            <span class="toast-title">${badgeText}</span>
            <span class="toast-conf">${confPct}% AI</span>
          </div>
          <button class="toast-close-btn" title="Dismiss">✕</button>
        </div>
        <div class="toast-body-row">
          <div class="toast-thumb-box">
            <img src="${imgUrl}" alt="Detection Snapshot" onerror="this.src='/static/img/placeholder.jpg'">
          </div>
          <div class="toast-info">
            <div class="toast-coords-val">
              <span>📍</span> <span>${lat.toFixed(6)}°N, ${lon.toFixed(6)}°E</span>
            </div>
            <div class="toast-time-val">
              <span>⏱️</span> <span>${timeStr}</span>
            </div>
            <div class="toast-lora-val">
              <span>📡</span> <span>LoRa Link: ${loraRssi} [${droneId}]</span>
            </div>
            <div class="toast-cta-hint">
              👉 CLICK TO LOCATE ON MAP & VIEW SNAPSHOT
            </div>
          </div>
        </div>
      </div>
    `;

    // Clicking toast focuses marker on map and opens inspection modal
    toast.addEventListener('click', (e) => {
      if (e.target.classList.contains('toast-close-btn')) {
        toast.remove();
        return;
      }
      if (window.tacticalMap && lat && lon) {
        window.tacticalMap.focusDetection(detId, lat, lon);
      }
      if (window.viewSnapshot) {
        window.viewSnapshot(detId);
      }
    });

    const closeBtn = toast.querySelector('.toast-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toast.remove();
      });
    }

    container.insertBefore(toast, container.firstChild);

    // Keep max 3 toasts at a time
    if (container.children.length > 3) {
      container.removeChild(container.lastChild);
    }

    // Auto-remove after 12 seconds
    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(60px)';
        toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        setTimeout(() => toast.remove(), 350);
      }
    }, 12000);
  }
}
