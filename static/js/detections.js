/**
 * OVERLORD AI TARGET DETECTION & SNAPSHOT GALLERY CONTROLLER
 * Manages target snapshot cards, LoRa transmission telemetry, and modal inspection.
 */

class DetectionManager {
  constructor() {
    this.detections = [];
    this.currentModalDetection = null;
  }

  init() {
    this.fetchDetections();
    // Poll every 5 seconds as a secondary sync
    setInterval(() => this.fetchDetections(), 5000);
  }

  async fetchDetections() {
    try {
      const resp = await fetch('/api/detections?limit=30');
      const data = await resp.json();
      this.detections = data;
      this.renderList();
    } catch (err) {
      console.error("Failed to load detections:", err);
    }
  }

  renderList() {
    const container = document.getElementById('detections-stream-list');
    if (!container) return;

    if (this.detections.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); font-size: 0.72rem; padding: 20px 0; font-family: Orbitron;">
          AWAITING AI TARGET ACQUISITIONS...
        </div>
      `;
      return;
    }

    container.innerHTML = this.detections.map(d => {
      const isLifeSign = d.target_type && d.target_type.includes("LIFE");
      const cardClass = isLifeSign ? "detect-card life-sign" : "detect-card casualty";
      const badgeClass = isLifeSign ? "detect-badge life-sign" : "detect-badge casualty";
      const label = isLifeSign ? "SURVIVOR (LIFE-SIGN)" : "CASUALTY (DECEASED)";
      const timeStr = d.timestamp ? d.timestamp.substring(11, 19) : "--:--:--";

      return `
        <div class="${cardClass}" onclick="window.viewSnapshot('${d.id}')">
          <div class="detect-top">
            <span class="${badgeClass}">${label}</span>
            <span style="color: var(--accent-cyan); font-weight: bold;">${(d.confidence * 100).toFixed(0)}%</span>
          </div>
          <div class="detect-meta">
            <span>[${d.drone_id}] POS: ${d.latitude.toFixed(5)}, ${d.longitude.toFixed(5)}</span>
            <span>${timeStr} UTC</span>
          </div>
          <div class="detect-lora-info">
            <span>📡 LoRa: ${d.lora_rssi.toFixed(1)} dBm | SNR: ${d.lora_snr.toFixed(1)} dB | Chunks: ${d.lora_packets_received}</span>
          </div>
        </div>
      `;
    }).join('');
  }

  async openModal(detectionId) {
    let d = this.detections.find(x => x.id === detectionId || x.detection_id === detectionId);
    if (!d) {
      try {
        const resp = await fetch(`/api/detections/${detectionId}`);
        if (resp.ok) {
          d = await resp.json();
        } else {
          const listResp = await fetch(`/api/detections?limit=100`);
          const all = await listResp.json();
          d = all.find(x => x.id === detectionId || x.detection_id === detectionId);
        }
      } catch (e) {
        console.error("Failed to load detection details:", e);
      }
    }
    if (!d) return;

    this.currentModalDetection = d;
    const isLifeSign = d.target_type && (
      d.target_type.toUpperCase().includes("LIFE") || 
      d.target_type.toUpperCase().includes("SURVIVOR")
    );

    const titleEl = document.getElementById('modal-target-title');
    if (titleEl) {
      titleEl.innerText = isLifeSign ? "SURVIVOR LIFE-SIGN SNAPSHOT ACQUIRED" : "CASUALTY TARGET SNAPSHOT RECORDED";
      titleEl.style.color = isLifeSign ? "#00ff9d" : "#ff3366";
    }

    // Set high-resolution snapshot image
    const imgEl = document.getElementById('modal-snapshot-img');
    if (imgEl) {
      imgEl.src = `/api/snapshots/${d.id || d.detection_id}`;
    }

    // Fill metadata fields
    const lat = Number(d.latitude || d.lat || 0);
    const lon = Number(d.longitude || d.lon || 0);
    const timeStr = d.timestamp || (new Date().toISOString().replace('T', ' ').substring(0, 19) + " UTC");

    if (document.getElementById('modal-field-id')) {
      document.getElementById('modal-field-id').innerText = d.id || d.detection_id;
    }
    if (document.getElementById('modal-field-drone')) {
      document.getElementById('modal-field-drone').innerText = d.drone_id || "UAV-ALPHA";
    }
    if (document.getElementById('modal-field-conf')) {
      document.getElementById('modal-field-conf').innerText = `${((d.confidence || 0.9) * 100).toFixed(1)}%`;
    }
    if (document.getElementById('modal-field-coords')) {
      document.getElementById('modal-field-coords').innerText = `${lat.toFixed(6)}°N, ${lon.toFixed(6)}°E`;
    }
    if (document.getElementById('modal-field-timestamp')) {
      document.getElementById('modal-field-timestamp').innerText = timeStr;
    }
    if (document.getElementById('modal-field-lora')) {
      const r = d.lora_rssi !== undefined ? `${Number(d.lora_rssi).toFixed(1)} dBm` : "-72.0 dBm";
      const s = d.lora_snr !== undefined ? `${Number(d.lora_snr).toFixed(1)} dB` : "9.5 dB";
      document.getElementById('modal-field-lora').innerText = `${r} (SNR: ${s})`;
    }
    if (document.getElementById('modal-field-status')) {
      document.getElementById('modal-field-status').innerText = d.status || "UNCONFIRMED";
    }

    // Show modal
    const modal = document.getElementById('snapshot-modal');
    if (modal) {
      modal.style.display = 'flex';
    }
  }

  closeModal() {
    const modal = document.getElementById('snapshot-modal');
    if (modal) {
      modal.style.display = 'none';
    }
    this.currentModalDetection = null;
  }

  async verifyTarget() {
    if (!this.currentModalDetection) return;
    try {
      const id = this.currentModalDetection.id || this.currentModalDetection.detection_id;
      await fetch(`/api/detections/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: "VERIFIED_CONFIRMED" })
      });
      const stEl = document.getElementById('modal-field-status');
      if (stEl) stEl.innerText = "VERIFIED_CONFIRMED";
      this.fetchDetections();
    } catch (e) {
      console.error(e);
    }
  }

  async dispatchEvac() {
    if (!this.currentModalDetection) return;
    try {
      const id = this.currentModalDetection.id || this.currentModalDetection.detection_id;
      await fetch(`/api/detections/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: "EVAC_DISPATCHED", notes: "Ground extraction unit en route" })
      });
      const stEl = document.getElementById('modal-field-status');
      if (stEl) stEl.innerText = "EVAC_DISPATCHED";
      this.fetchDetections();
      alert("Tactical QRF & Evacuation team dispatched with target coordinates!");
    } catch (e) {
      console.error(e);
    }
  }
}

// Global viewer binding
window.viewSnapshot = function(id) {
  if (window.detectionManager) {
    window.detectionManager.openModal(id);
  }
};

window.locateDetectionOnMap = function() {
  if (window.detectionManager && window.detectionManager.currentModalDetection) {
    const d = window.detectionManager.currentModalDetection;
    const lat = Number(d.latitude || d.lat || 0);
    const lon = Number(d.longitude || d.lon || 0);
    const id = d.id || d.detection_id;
    window.detectionManager.closeModal();
    if (window.tacticalMap && lat && lon) {
      window.tacticalMap.focusDetection(id, lat, lon);
    }
  }
};
