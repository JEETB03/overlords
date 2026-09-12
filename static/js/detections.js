/**
 * OVERLORD AI TARGET DETECTION & LORA LINK MISSION GALLERY CONTROLLER
 * Manages target snapshot cards, LoRa transmission telemetry, and modal inspection.
 */

class DetectionManager {
  constructor() {
    this.detections = [];
    this.currentModalDetection = null;
    this.activeFilter = 'all';
    this.isSyncing = false;
  }

  init() {
    this.fetchDetections();
    this.pollLoRaStatus();
    this.bindEvents();

    // Poll every 5 seconds as a secondary sync
    setInterval(() => {
      this.fetchDetections();
      this.pollLoRaStatus();
    }, 5000);
  }

  bindEvents() {
    // Filter tabs
    const tabs = document.querySelectorAll('.filter-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        tabs.forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        this.activeFilter = e.target.getAttribute('data-filter') || 'all';
        this.renderList();
      });
    });

    // Manual Sync button
    const btnSync = document.getElementById('btn-sync-lora-rx');
    if (btnSync) {
      btnSync.addEventListener('click', () => this.syncLoRaLink());
    }

    // Scenario LoRa Link sync button
    const btnSimSync = document.getElementById('sim-btn-sync-lora');
    if (btnSimSync) {
      btnSimSync.addEventListener('click', () => this.syncLoRaLink());
    }
  }

  async pollLoRaStatus() {
    try {
      const resp = await fetch('/api/lora-link/status');
      if (resp.ok) {
        const data = await resp.json();
        const dot = document.getElementById('lora-link-dot');
        const text = document.getElementById('lora-link-text');
        const pill = document.getElementById('lora-link-status-pill');

        if (dot && text) {
          if (data.online) {
            dot.className = "status-dot pulse";
            dot.style.background = "#00ff9d";
            dot.style.boxShadow = "0 0 8px #00ff9d";
            text.innerText = `ONLINE (${data.synced_count || 0} RX)`;
            text.style.color = "var(--accent-green)";
            if (pill) {
              pill.title = `LoRa Link Station Active: ${data.base_url} (Last sync: ${new Date(data.last_sync_time * 1000).toLocaleTimeString()})`;
            }
          } else {
            dot.className = "status-dot red";
            dot.style.background = "#ff3366";
            dot.style.boxShadow = "0 0 8px #ff3366";
            text.innerText = "OFFLINE";
            text.style.color = "var(--accent-red)";
            if (pill) {
              pill.title = `LoRa Link Station Offline: ${data.base_url}`;
            }
          }
        }
      }
    } catch (e) {
      console.debug("LoRa status poll error:", e);
    }
  }

  async syncLoRaLink() {
    if (this.isSyncing) return;
    this.isSyncing = true;
    const btn = document.getElementById('btn-sync-lora-rx');
    const simBtn = document.getElementById('sim-btn-sync-lora');
    if (btn) btn.innerText = "⏳ Syncing...";
    if (simBtn) simBtn.innerText = "⏳ Contacting LoRa Station...";

    try {
      const resp = await fetch('/api/lora-link/sync', { method: 'POST' });
      const result = await resp.json();
      console.log("LoRa Link sync response:", result);
      await this.fetchDetections();
      await this.pollLoRaStatus();
      if (window.tacticalMap && window.tacticalMap.loadLoRaReconTrack) {
        window.tacticalMap.loadLoRaReconTrack();
      }
    } catch (e) {
      console.error("LoRa Link sync failed:", e);
    } finally {
      this.isSyncing = false;
      if (btn) btn.innerText = "🔄 Sync RX";
      if (simBtn) simBtn.innerText = "🛰️ Sync LoRa Link Missions (172.16.59.210)";
    }
  }

  async fetchDetections() {
    try {
      const resp = await fetch('/api/detections?limit=50');
      const data = await resp.json();
      this.detections = data;
      this.renderList();
      if (window.tacticalMap && window.tacticalMap.loadLoRaReconTrack) {
        window.tacticalMap.loadLoRaReconTrack();
      }
    } catch (err) {
      console.error("Failed to load detections:", err);
    }
  }

  renderList() {
    const container = document.getElementById('detections-stream-list');
    if (!container) return;

    let filtered = this.detections;
    if (this.activeFilter === 'lora') {
      filtered = this.detections.filter(d => 
        d.target_type === 'LORA_MISSION' || 
        d.target_type === 'SURVEY' || 
        (d.notes && d.notes.includes('LoRa Link'))
      );
    } else if (this.activeFilter === 'sim') {
      filtered = this.detections.filter(d => 
        d.target_type !== 'LORA_MISSION' && 
        d.target_type !== 'SURVEY' && 
        !(d.notes && d.notes.includes('LoRa Link'))
      );
    }

    if (filtered.length === 0) {
      const emptyMsg = this.activeFilter === 'lora' 
        ? "NO LORA LINK MISSIONS INGESTED YET. CLICK 'SYNC RX' TO POLL STATION."
        : "AWAITING AI TARGET ACQUISITIONS...";
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); font-size: 0.72rem; padding: 25px 10px; font-family: Orbitron; line-height: 1.5;">
          ${emptyMsg}
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(d => {
      const isLoraLink = d.target_type === 'LORA_MISSION' || (d.notes && d.notes.includes('LoRa Link'));
      const isLifeSign = !isLoraLink && d.target_type && d.target_type.includes("LIFE");

      let cardClass = "detect-card";
      let badgeClass = "detect-badge";
      let label = "";

      if (isLoraLink) {
        cardClass += " lora-mission";
        badgeClass += " lora-mission";
        label = "🛰️ LORA RX RECON";
      } else if (isLifeSign) {
        cardClass += " life-sign";
        badgeClass += " life-sign";
        label = "SURVIVOR (LIFE-SIGN)";
      } else {
        cardClass += " casualty";
        badgeClass += " casualty";
        label = "CASUALTY (DECEASED)";
      }

      const timeStr = d.timestamp ? d.timestamp.substring(11, 19) : "--:--:--";
      const confText = isLoraLink ? "100% RX" : `${(d.confidence * 100).toFixed(0)}%`;
      const lat = Number(d.latitude || d.lat || 0);
      const lon = Number(d.longitude || d.lon || 0);
      const mid = d.mission_id || (d.notes && d.notes.includes("LoRa Link Mission:") ? d.notes.split("LoRa Link Mission:")[1].split("|")[0].trim() : "");

      // Clean metadata snippet for bottom info line
      let loraSnippet = `📡 LoRa: ${d.lora_rssi ? d.lora_rssi.toFixed(1) : '-68.0'} dBm | SNR: ${d.lora_snr ? d.lora_snr.toFixed(1) : '10.5'} dB`;
      if (isLoraLink && d.notes) {
        const camMatch = d.notes.match(/Camera:\s*([^|]+)/);
        const cam = camMatch ? camMatch[1].trim() : "RunCam";
        loraSnippet = `📡 LoRa RX | Cam: ${cam} | POS: ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
      }

      return `
        <div class="${cardClass}" onclick="window.viewSnapshot('${d.id}')">
          <div class="detect-top">
            <span class="${badgeClass}">${label}</span>
            <span style="color: var(--accent-cyan); font-weight: bold; font-family: Orbitron; font-size: 0.75rem;">${confText}</span>
          </div>
          <div class="detect-meta">
            <span>[${d.drone_id}] ${isLoraLink && mid ? mid : `POS: ${lat.toFixed(5)}, ${lon.toFixed(5)}`}</span>
            <span>${timeStr} UTC</span>
          </div>
          <div class="detect-lora-info">
            <span>${loraSnippet}</span>
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
    const isLoraLink = d.target_type === 'LORA_MISSION' || (d.notes && d.notes.includes('LoRa Link'));
    const isLifeSign = !isLoraLink && d.target_type && (
      d.target_type.toUpperCase().includes("LIFE") || 
      d.target_type.toUpperCase().includes("SURVIVOR")
    );

    const titleEl = document.getElementById('modal-target-title');
    if (titleEl) {
      if (isLoraLink) {
        titleEl.innerText = "LORA LINK RECON SURVEY MISSION INSPECTION";
        titleEl.style.color = "#00f0ff";
      } else if (isLifeSign) {
        titleEl.innerText = "SURVIVOR LIFE-SIGN SNAPSHOT ACQUIRED";
        titleEl.style.color = "#00ff9d";
      } else {
        titleEl.innerText = "CASUALTY TARGET SNAPSHOT RECORDED";
        titleEl.style.color = "#ff3366";
      }
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
      document.getElementById('modal-field-drone').innerText = d.drone_id || "DRONE-01";
    }
    if (document.getElementById('modal-field-conf')) {
      document.getElementById('modal-field-conf').innerText = isLoraLink ? "100% (RECONSTRUCTED)" : `${((d.confidence || 0.9) * 100).toFixed(1)}%`;
    }
    if (document.getElementById('modal-field-coords')) {
      document.getElementById('modal-field-coords').innerText = `${lat.toFixed(6)}°N, ${lon.toFixed(6)}°E`;
    }
    if (document.getElementById('modal-field-timestamp')) {
      document.getElementById('modal-field-timestamp').innerText = timeStr;
    }
    if (document.getElementById('modal-field-lora')) {
      const r = d.lora_rssi !== undefined ? `${Number(d.lora_rssi).toFixed(1)} dBm` : "-68.0 dBm";
      const s = d.lora_snr !== undefined ? `${Number(d.lora_snr).toFixed(1)} dB` : "10.5 dB";
      document.getElementById('modal-field-lora').innerText = `${r} (SNR: ${s})`;
    }
    if (document.getElementById('modal-field-camera')) {
      let cam = "Thermal / EO Flir";
      if (d.notes && d.notes.includes("Camera:")) {
        const m = d.notes.match(/Camera:\s*([^|]+)/);
        if (m) cam = m[1].trim();
      }
      document.getElementById('modal-field-camera').innerText = cam;
    }
    if (document.getElementById('modal-field-notes')) {
      document.getElementById('modal-field-notes').innerText = d.notes || "Autonomous survey capture.";
    }
    if (document.getElementById('modal-field-status')) {
      document.getElementById('modal-field-status').innerText = d.status || "CONFIRMED";
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
