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
    let d = this.detections.find(x => x.id === detectionId);
    if (!d) {
      try {
        const resp = await fetch(`/api/detections?limit=100`);
        const all = await resp.json();
        d = all.find(x => x.id === detectionId);
      } catch (e) {}
    }
    if (!d) return;

    this.currentModalDetection = d;
    const isLifeSign = d.target_type && d.target_type.includes("LIFE");

    document.getElementById('modal-target-title').innerText = isLifeSign ? "SURVIVOR LIFE-SIGN SNAPSHOT" : "CASUALTY TARGET SNAPSHOT";
    document.getElementById('modal-target-title').style.color = isLifeSign ? "#00ff9d" : "#ff3366";

    // Set image
    const imgEl = document.getElementById('modal-snapshot-img');
    imgEl.src = `/api/snapshots/${d.id}`;

    // Fill metadata
    document.getElementById('modal-field-id').innerText = d.id.substring(0, 8);
    document.getElementById('modal-field-drone').innerText = d.drone_id;
    document.getElementById('modal-field-conf').innerText = `${(d.confidence * 100).toFixed(1)}%`;
    document.getElementById('modal-field-coords').innerText = `${d.latitude.toFixed(6)}°N, ${d.longitude.toFixed(6)}°E`;
    document.getElementById('modal-field-lora').innerText = `${d.lora_rssi} dBm (SNR: ${d.lora_snr}dB)`;
    document.getElementById('modal-field-status').innerText = d.status;

    // Show modal
    document.getElementById('snapshot-modal').style.display = 'flex';
  }

  closeModal() {
    document.getElementById('snapshot-modal').style.display = 'none';
    this.currentModalDetection = null;
  }

  async verifyTarget() {
    if (!this.currentModalDetection) return;
    try {
      await fetch(`/api/detections/${this.currentModalDetection.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: "VERIFIED_CONFIRMED" })
      });
      document.getElementById('modal-field-status').innerText = "VERIFIED_CONFIRMED";
      this.fetchDetections();
    } catch (e) {
      console.error(e);
    }
  }

  async dispatchEvac() {
    if (!this.currentModalDetection) return;
    try {
      await fetch(`/api/detections/${this.currentModalDetection.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: "EVAC_DISPATCHED", notes: "Ground extraction unit en route" })
      });
      document.getElementById('modal-field-status').innerText = "EVAC_DISPATCHED";
      this.fetchDetections();
      alert("Ground Quick Reaction Force & Evac unit alerted with coordinates!");
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
