/**
 * OVERLORD TACTICAL MAP & DUAL DRONE GEOFENCE CONTROLLER
 * Handles high-res satellite mapping, geofence polygon drawing,
 * and autonomous deployment & traversal planning for both UAV and UGV
 * starting from their last known locations to the newly plotted geofence.
 */

class TacticalMap {
  constructor(containerId, initialLat, initialLon) {
    this.containerId = containerId;
    this.initialLat = initialLat || 28.613939;
    this.initialLon = initialLon || 77.209021;
    
    this.map = null;
    this.uavMarker = null;
    this.ugvMarker = null;
    this.uavTrail = null;
    this.ugvTrail = null;
    this.uavHistory = [];
    this.ugvHistory = [];
    
    // Last Known Drone Positions
    this.lastUavPos = [this.initialLat, this.initialLon];
    this.lastUgvPos = [this.initialLat - 0.00045, this.initialLon + 0.00060];

    // Geofence Drawing State
    this.isDrawing = false;
    this.drawPoints = [];
    this.drawTempMarkers = [];
    this.drawPolyline = null;
    this.activeGeofenceLayer = null;
    this.waypointsLayerGroup = null;
    this.detectionsLayerGroup = null;
    this.detectionMarkers = {};

    this.currentPolygon = [];
    this.currentUavWaypoints = [];
    this.currentUgvWaypoints = [];
  }

  init() {
    this.map = L.map(this.containerId, {
      center: [this.initialLat, this.initialLon],
      zoom: 17,
      zoomControl: false,
      attributionControl: false
    });

    // 1. High-Resolution Photorealistic Satellite Layer (Default)
    const satelliteLayer = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 19,
        attribution: 'Esri World Imagery'
      }
    );

    // 2. OpenStreetMap Layer
    const osmLayer = L.tileLayer(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }
    );

    // Add Satellite by default
    satelliteLayer.addTo(this.map);

    // Layer Switcher Control
    const baseMaps = {
      "🛰️ Satellite Imagery": satelliteLayer,
      "🗺️ OpenStreetMap": osmLayer
    };

    L.control.layers(baseMaps, null, { position: 'bottomleft' }).addTo(this.map);

    // Zoom control on bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(this.map);

    // Layer Groups
    this.waypointsLayerGroup = L.layerGroup().addTo(this.map);
    this.detectionsLayerGroup = L.layerGroup().addTo(this.map);

    // Drone Trails
    this.uavTrail = L.polyline([], {
      color: '#00f0ff',
      weight: 2,
      opacity: 0.6,
      dashArray: '4, 4'
    }).addTo(this.map);

    this.ugvTrail = L.polyline([], {
      color: '#00ff9d',
      weight: 2,
      opacity: 0.6,
      dashArray: '3, 5'
    }).addTo(this.map);

    // Initialize Markers
    this.initDroneMarkers();

    // Setup Drawing Click Handlers
    this.map.on('click', (e) => this.onMapClick(e));

    // Load active geofence if already exists on server
    this.fetchActiveGeofence();

    // Preload recorded detections onto map
    this.loadExistingDetections();
  }

  initDroneMarkers() {
    const uavIcon = L.divIcon({
      className: 'drone-icon-container',
      html: `
        <div id="uav-hud-icon" style="transform: rotate(45deg); transition: transform 0.2s linear;">
          <svg width="36" height="36" viewBox="0 0 36 36">
            <polygon points="18,2 32,32 18,25 4,32" fill="rgba(0, 240, 255, 0.4)" stroke="#00f0ff" stroke-width="2"/>
            <circle cx="18" cy="18" r="4" fill="#00f0ff"/>
          </svg>
        </div>
        <div style="font-family: Orbitron, monospace; font-size: 10px; color: #00f0ff; background: rgba(8,12,20,0.85); border: 1px solid #00f0ff; padding: 1px 4px; border-radius: 2px; white-space: nowrap; margin-top: 2px;">
          UAV-ALPHA [65m]
        </div>
      `,
      iconSize: [36, 50],
      iconAnchor: [18, 18]
    });

    const ugvIcon = L.divIcon({
      className: 'drone-icon-container',
      html: `
        <div id="ugv-hud-icon" style="transform: rotate(180deg); transition: transform 0.2s linear;">
          <svg width="32" height="32" viewBox="0 0 32 32">
            <rect x="6" y="4" width="20" height="24" rx="3" fill="rgba(0, 255, 157, 0.4)" stroke="#00ff9d" stroke-width="2"/>
            <rect x="2" y="6" width="4" height="20" rx="1" fill="#00ff9d"/>
            <rect x="26" y="6" width="4" height="20" rx="1" fill="#00ff9d"/>
            <circle cx="16" cy="16" r="3" fill="#ffffff"/>
          </svg>
        </div>
        <div style="font-family: Orbitron, monospace; font-size: 9px; color: #00ff9d; background: rgba(8,12,20,0.85); border: 1px solid #00ff9d; padding: 1px 4px; border-radius: 2px; white-space: nowrap; margin-top: 2px;">
          UGV-BRAVO
        </div>
      `,
      iconSize: [32, 45],
      iconAnchor: [16, 16]
    });

    this.uavMarker = L.marker([this.initialLat, this.initialLon], { icon: uavIcon }).addTo(this.map);
    this.ugvMarker = L.marker([this.initialLat - 0.00045, this.initialLon + 0.00060], { icon: ugvIcon }).addTo(this.map);
  }

  updatePositions(uavData, ugvData) {
    if (uavData && uavData.lat && uavData.lon) {
      const uavPos = [uavData.lat, uavData.lon];
      this.lastUavPos = uavPos;
      this.uavMarker.setLatLng(uavPos);
      
      const uavEl = document.getElementById('uav-hud-icon');
      if (uavEl && uavData.heading !== undefined) {
        uavEl.style.transform = `rotate(${uavData.heading}deg)`;
      }

      this.uavHistory.push(uavPos);
      if (this.uavHistory.length > 100) this.uavHistory.shift();
      this.uavTrail.setLatLngs(this.uavHistory);
    }

    if (ugvData && ugvData.lat && ugvData.lon) {
      const ugvPos = [ugvData.lat, ugvData.lon];
      this.lastUgvPos = ugvPos;
      this.ugvMarker.setLatLng(ugvPos);

      const ugvEl = document.getElementById('ugv-hud-icon');
      if (ugvEl && ugvData.heading !== undefined) {
        ugvEl.style.transform = `rotate(${ugvData.heading}deg)`;
      }

      this.ugvHistory.push(ugvPos);
      if (this.ugvHistory.length > 80) this.ugvHistory.shift();
      this.ugvTrail.setLatLngs(this.ugvHistory);
    }
  }

  // GEOFENCE DRAWING TOOL
  startDrawingGeofence() {
    this.isDrawing = true;
    this.drawPoints = [];
    this.clearDrawGraphics();
    
    const btnDraw = document.getElementById('btn-draw-geofence');
    if (btnDraw) {
      btnDraw.classList.add('btn-amber');
      btnDraw.innerHTML = '<span class="status-dot amber pulse"></span> Click Map to Draw (3+ pts)';
    }
    document.getElementById('map-status-text').innerText = 'DRAW MODE: Click on map to add boundary vertices. Double-click or click "Close Polygon" to complete.';
  }

  onMapClick(e) {
    if (!this.isDrawing) return;

    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    this.drawPoints.push([lat, lng]);

    const vertexMarker = L.circleMarker([lat, lng], {
      radius: 5,
      color: '#ffb800',
      fillColor: '#ffb800',
      fillOpacity: 0.9
    }).addTo(this.map);
    this.drawTempMarkers.push(vertexMarker);

    if (!this.drawPolyline) {
      this.drawPolyline = L.polyline(this.drawPoints, {
        color: '#ffb800',
        weight: 2,
        dashArray: '5, 5'
      }).addTo(this.map);
    } else {
      this.drawPolyline.setLatLngs(this.drawPoints);
    }

    if (this.drawPoints.length >= 3) {
      document.getElementById('btn-finish-geofence').style.display = 'inline-flex';
    }
  }

  finishDrawingGeofence() {
    if (this.drawPoints.length < 3) {
      alert("Please click at least 3 points to form a polygon geofence.");
      return;
    }

    this.isDrawing = false;
    this.currentPolygon = [...this.drawPoints];
    this.renderPolygonGeofence(this.currentPolygon);
    this.clearDrawGraphics();

    const btnDraw = document.getElementById('btn-draw-geofence');
    if (btnDraw) {
      btnDraw.classList.remove('btn-amber');
      btnDraw.innerHTML = 'Plot Geofence';
    }
    document.getElementById('btn-finish-geofence').style.display = 'none';
    document.getElementById('btn-gen-path').style.display = 'inline-flex';
    document.getElementById('btn-deploy-mission').style.display = 'inline-flex';

    document.getElementById('map-status-text').innerText = 
      `Geofence defined (${this.currentPolygon.length} vertices). Ready to plan UAV & UGV deployment from last known locations.`;
  }

  clearDrawGraphics() {
    this.drawTempMarkers.forEach(m => this.map.removeLayer(m));
    this.drawTempMarkers = [];
    if (this.drawPolyline) {
      this.map.removeLayer(this.drawPolyline);
      this.drawPolyline = null;
    }
  }

  renderPolygonGeofence(polygonCoords) {
    if (this.activeGeofenceLayer) {
      this.map.removeLayer(this.activeGeofenceLayer);
    }

    this.activeGeofenceLayer = L.polygon(polygonCoords, {
      color: '#00f0ff',
      weight: 2,
      fillColor: '#00f0ff',
      fillOpacity: 0.12,
      dashArray: '6, 6'
    }).addTo(this.map);

    this.map.fitBounds(this.activeGeofenceLayer.getBounds(), { padding: [50, 50] });
  }

  async generateTraversalPath() {
    if (this.currentPolygon.length < 3) {
      alert("Draw a geofence on the map first.");
      return;
    }

    try {
      const resp = await fetch('/api/geofence/generate-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: "Zone Alpha",
          polygon: this.currentPolygon,
          lane_spacing_meters: 25.0,
          altitude_meters: 65.0,
          uav_start: this.lastUavPos,
          ugv_start: this.lastUgvPos
        })
      });

      const data = await resp.json();
      if (data.status === "SUCCESS") {
        this.currentUavWaypoints = data.uav_waypoints || [];
        this.currentUgvWaypoints = data.ugv_waypoints || [];
        
        this.renderDualMissions(
          this.currentUavWaypoints,
          this.currentUgvWaypoints,
          data.uav_meta,
          data.ugv_meta,
          this.lastUavPos,
          this.lastUgvPos
        );
        
        document.getElementById('map-status-text').innerText = 
          `DEPLOYMENT PLANNED: UAV Ingress: ${data.uav_meta?.transit_distance_m || 0}m + ${data.uav_waypoints_count} Grid WPs | UGV Ingress: ${data.ugv_meta?.transit_distance_m || 0}m + ${data.ugv_waypoints_count} Perimeter WPs (${data.area_hectares} ha)`;
      }
    } catch (err) {
      console.error("Path generation error:", err);
    }
  }

  renderDualMissions(uavWps, ugvWps, uavMeta, ugvMeta, uavStart, ugvStart) {
    this.waypointsLayerGroup.clearLayers();

    // 1. RENDER UAV MISSION
    if (uavWps && uavWps.length > 0) {
      // Ingress / Transit Leg from last known UAV position to entry waypoint
      const entryWp = uavWps[0];
      if (uavStart) {
        const uavTransitLine = L.polyline([uavStart, [entryWp.lat, entryWp.lng]], {
          color: '#00f0ff',
          weight: 2,
          opacity: 0.9,
          dashArray: '6, 6'
        });
        uavTransitLine.bindTooltip("UAV Transit / Ingress Leg", { sticky: true });
        this.waypointsLayerGroup.addLayer(uavTransitLine);
      }

      // Interior Lawnmower Survey Grid
      const surveyCoords = uavWps.map(wp => [wp.lat, wp.lng]);
      const uavPathLine = L.polyline(surveyCoords, {
        color: '#00f0ff',
        weight: 2,
        opacity: 0.85
      });
      this.waypointsLayerGroup.addLayer(uavPathLine);

      // UAV Waypoint Nodes
      uavWps.forEach((wp) => {
        const isTransit = wp.action === "TRANSIT";
        const nodeColor = isTransit ? "#ffb800" : "#00f0ff";
        const nodeText = isTransit ? "IN" : `U${wp.id}`;

        const wpIcon = L.divIcon({
          className: 'wp-node',
          html: `<div style="width: 18px; height: 18px; border-radius: 50%; background: #080c14; border: 2px solid ${nodeColor}; color: ${nodeColor}; font-family: Orbitron; font-size: 8px; font-weight: bold; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 6px ${nodeColor};">${nodeText}</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9]
        });
        const marker = L.marker([wp.lat, wp.lng], { icon: wpIcon });
        marker.bindTooltip(`UAV WP #${wp.id} [${wp.action}] - ${wp.description || ''}`);
        this.waypointsLayerGroup.addLayer(marker);
      });
    }

    // 2. RENDER UGV MISSION
    if (ugvWps && ugvWps.length > 0) {
      // Ingress / Transit Leg from last known UGV position to geofence perimeter
      const ugvEntryWp = ugvWps[0];
      if (ugvStart) {
        const ugvTransitLine = L.polyline([ugvStart, [ugvEntryWp.lat, ugvEntryWp.lng]], {
          color: '#00ff9d',
          weight: 2,
          opacity: 0.9,
          dashArray: '5, 5'
        });
        ugvTransitLine.bindTooltip("UGV Transit / Ingress Leg", { sticky: true });
        this.waypointsLayerGroup.addLayer(ugvTransitLine);
      }

      // Perimeter Patrol Loop
      const ugvCoords = ugvWps.map(wp => [wp.lat, wp.lng]);
      const ugvPathLine = L.polyline(ugvCoords, {
        color: '#00ff9d',
        weight: 2,
        opacity: 0.75
      });
      this.waypointsLayerGroup.addLayer(ugvPathLine);

      // UGV Waypoint Nodes
      ugvWps.forEach((wp) => {
        const isTransit = wp.action === "TRANSIT";
        const nodeColor = isTransit ? "#ffb800" : "#00ff9d";
        const nodeText = isTransit ? "IN" : `G${wp.id}`;

        const wpIcon = L.divIcon({
          className: 'wp-node',
          html: `<div style="width: 18px; height: 18px; border-radius: 4px; background: #080c14; border: 2px solid ${nodeColor}; color: ${nodeColor}; font-family: Orbitron; font-size: 8px; font-weight: bold; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 6px ${nodeColor};">${nodeText}</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9]
        });
        const marker = L.marker([wp.lat, wp.lng], { icon: wpIcon });
        marker.bindTooltip(`UGV WP #${wp.id} [${wp.action}] - ${wp.description || ''}`);
        this.waypointsLayerGroup.addLayer(marker);
      });
    }
  }

  async deployMissionToDrone() {
    if (this.currentPolygon.length < 3) {
      alert("Please draw a geofence first.");
      return;
    }

    try {
      const resp = await fetch('/api/geofence/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: "Zone Alpha",
          polygon: this.currentPolygon,
          lane_spacing_meters: 25.0,
          altitude_meters: 65.0,
          uav_start: this.lastUavPos,
          ugv_start: this.lastUgvPos
        })
      });

      const data = await resp.json();
      if (data.status === "DISPATCHED") {
        this.currentUavWaypoints = data.uav_waypoints || [];
        this.currentUgvWaypoints = data.ugv_waypoints || [];
        
        this.renderDualMissions(
          this.currentUavWaypoints,
          this.currentUgvWaypoints,
          data.uav_meta,
          data.ugv_meta,
          this.lastUavPos,
          this.lastUgvPos
        );

        document.getElementById('map-status-text').innerText = 
          `🚀 MISSIONS DISPATCHED! UAV-ALPHA & UGV-BRAVO actively navigating to and traversing the newly designated geofence!`;
      }
    } catch (err) {
      console.error("Mission dispatch error:", err);
    }
  }

  async fetchActiveGeofence() {
    try {
      const resp = await fetch('/api/geofence/active');
      const data = await resp.json();
      if (data.active && data.polygon && data.polygon.length >= 3) {
        this.currentPolygon = data.polygon;
        this.renderPolygonGeofence(data.polygon);
        
        this.currentUavWaypoints = data.uav_waypoints || data.waypoints || [];
        this.currentUgvWaypoints = data.ugv_waypoints || [];
        
        if (this.currentUavWaypoints.length > 0 || this.currentUgvWaypoints.length > 0) {
          this.renderDualMissions(
            this.currentUavWaypoints,
            this.currentUgvWaypoints,
            null,
            null,
            this.lastUavPos,
            this.lastUgvPos
          );
        }
      }
    } catch (e) {
      console.log("No active geofence found on server.");
    }
  }

  async loadExistingDetections() {
    try {
      const resp = await fetch('/api/detections?limit=50');
      const list = await resp.json();
      if (Array.isArray(list)) {
        list.forEach(det => this.addDetectionMarker(det, false));
      }
    } catch (e) {
      console.warn("Could not preload existing detections on map:", e);
    }
  }

  addDetectionMarker(detection, shouldFocus = false) {
    if (!detection) return;
    const detId = detection.id || detection.detection_id || ('det_' + Date.now());
    const lat = Number(detection.latitude || detection.lat || 0);
    const lon = Number(detection.longitude || detection.lon || 0);
    if (!lat || !lon) return;

    // Check if marker already exists for this detection
    if (this.detectionMarkers[detId]) {
      const existing = this.detectionMarkers[detId].marker;
      if (shouldFocus) {
        this.map.flyTo([lat, lon], Math.max(this.map.getZoom(), 17), { animate: true, duration: 0.9 });
        setTimeout(() => existing.openPopup(), 400);
      }
      return;
    }

    const isLifeSign = detection.target_type && (
      detection.target_type.toUpperCase().includes("LIFE") || 
      detection.target_type.toUpperCase().includes("SURVIVOR")
    );
    const color = isLifeSign ? "#00ff9d" : "#ff3366";
    const label = isLifeSign ? "SURVIVOR (LIFE-SIGN)" : "CASUALTY (DEADBODY)";
    const confPct = Math.round(Number(detection.confidence || 0.9) * 100);
    const timeStr = detection.timestamp || (new Date().toISOString().replace('T', ' ').substring(0, 19) + " UTC");
    const droneId = detection.drone_id || "UAV-ALPHA";
    const loraRssi = (detection.lora_rssi !== undefined && detection.lora_rssi !== null) ? `${Number(detection.lora_rssi).toFixed(1)} dBm` : "-72.0 dBm";
    const loraPackets = detection.lora_packets_received || detection.lora_packets || 8;
    const imgUrl = detection.image_url || `/api/snapshots/${detId}`;

    const pulseIcon = L.divIcon({
      className: 'tactical-marker-pin-wrap',
      html: `
        <div class="tactical-marker-pin ${isLifeSign ? 'life-sign' : 'casualty'}">
          <div class="pin-pulse"></div>
          <div class="pin-core">${isLifeSign ? '👤' : '⚠️'}</div>
          <div class="pin-label">${isLifeSign ? 'LIFE-SIGN' : 'CASUALTY'}</div>
        </div>
      `,
      iconSize: [32, 45],
      iconAnchor: [16, 20]
    });

    const marker = L.marker([lat, lon], { icon: pulseIcon });

    const popupHtml = `
      <div class="tactical-popup-box ${isLifeSign ? 'life-sign' : 'casualty'}">
        <div class="popup-title-bar">
          <span class="popup-tag">${label}</span>
          <span class="popup-conf">${confPct}% CONF</span>
        </div>
        <div class="popup-snapshot-wrap" onclick="window.viewSnapshot('${detId}')" title="Click to view high-res picture">
          <img src="${imgUrl}" alt="Detection Snapshot" onerror="this.src='/static/img/placeholder.jpg'">
          <div class="popup-click-overlay">🔍 CLICK TO INSPECT PICTURE</div>
        </div>
        <div class="popup-data-table">
          <div class="popup-row">
            <span class="popup-k">LAT-LONG:</span>
            <span class="popup-v coords">${lat.toFixed(6)}°N, ${lon.toFixed(6)}°E</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">TIMESTAMP:</span>
            <span class="popup-v time">${timeStr}</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">LORA LINK:</span>
            <span class="popup-v lora">${loraRssi} (${loraPackets} pkts)</span>
          </div>
          <div class="popup-row">
            <span class="popup-k">PLATFORM:</span>
            <span class="popup-v">${droneId}</span>
          </div>
        </div>
        <button class="popup-inspect-btn ${isLifeSign ? 'btn-life' : 'btn-cas'}" onclick="window.viewSnapshot('${detId}')">
          INSPECT PICTURE & COORDS
        </button>
      </div>
    `;

    marker.bindPopup(popupHtml, {
      maxWidth: 290,
      className: 'tactical-leaflet-popup',
      autoPan: true
    });

    marker.on('click', () => {
      marker.openPopup();
    });

    this.detectionsLayerGroup.addLayer(marker);
    this.detectionMarkers[detId] = { marker, lat, lon, data: detection };

    if (shouldFocus) {
      this.map.flyTo([lat, lon], Math.max(this.map.getZoom(), 17), {
        animate: true,
        duration: 1.0
      });
      setTimeout(() => {
        marker.openPopup();
      }, 450);
    }
  }

  focusDetection(detId, lat, lon) {
    if (detId && this.detectionMarkers[detId]) {
      const entry = this.detectionMarkers[detId];
      this.map.flyTo([entry.lat, entry.lon], Math.max(this.map.getZoom(), 17), {
        animate: true,
        duration: 0.9
      });
      setTimeout(() => entry.marker.openPopup(), 400);
    } else if (lat && lon) {
      this.map.flyTo([lat, lon], Math.max(this.map.getZoom(), 17), {
        animate: true,
        duration: 0.9
      });
    }
  }
}
