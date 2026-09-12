# OVERLORD // Autonomous UAV & UGV Tactical Command & Control (C2) Dashboard

OVERLORD is a high-performance, Python FastAPI-based Command and Control (C2) tactical dashboard engineered for operating autonomous aerial (UAV) and ground (UGV) drone fleets in real-time.

---

## Key Features

1. **Dual Live Analog Video Feeds with Tactical OSD**:
   - **UAV Stream**: Aerial FLIR thermal / EO perspective with authentic analog OSD (artificial horizon pitch ladder, altitude tape, groundspeed tape, compass heading bar, GPS readouts, battery voltage, CRT scanlines, and adjustable analog RF noise/static).
   - **UGV Stream**: Ground rover optical feed with LiDAR proximity radar widget, collision alerts, motor temperatures, and gear status.
   - Endpoints: `/api/stream/uav` and `/api/stream/ugv` (continuous MJPEG streaming).

2. **High-Resolution Satellite Imagery & Lawnmower Traversal Planning**:
   - Interactive tactical map with true-color photorealistic **High-Resolution Satellite Imagery** (Esri World Imagery) and a layer switcher for **OpenStreetMap**.
   - Plot arbitrary polygon geofences by clicking vertices directly on the map.
   - Computational geometry engine calculates interior boustrophedon (lawnmower) autonomous search waypoints, survey area (hectares / $m^2$), and estimated flight time.
   - One-click autonomous mission dispatch to the UAV autopilot.
   - Real-time Point-in-Polygon geofence breach detection with auditory and visual alarms.

3. **AI Target Detection & Snapshot Engine (Life-Signs / Casualties / Deadbodies)**:
   - Onboard AI targets (e.g. `LIFE_SIGN / SURVIVOR` or `CASUALTY / DEADBODY`) trigger high-resolution annotated snapshots.
   - Stored in database with timestamp, GPS coordinates (lat/lon), altitude, confidence score, bounding boxes, and LoRa packet metrics.
   - Interactive Modal Inspection: view snapshot, verify target classification, and dispatch ground extraction forces.

4. **LoRa Radio Protocol Simulation & Hardware Serial Bridge**:
   - Models low-bandwidth LoRa transmission (868.1 / 915.0 MHz, SF7-SF12, chunked packet fragmentation, CRC integrity check, RSSI, and SNR).
   - Reassembles progressive image packets transmitted over long-range radio.
   - Supports both USB serial transceivers (`/dev/ttyUSB0` SX1262/SX1276) and API gateway ingestion (`POST /api/lora/rx`).

5. **Multi-Backend Adaptive Database Layer**:
   - Configurable for **PostgreSQL** (`DATABASE_URL=postgresql+asyncpg://...`) and **ClickHouse** (`CLICKHOUSE_URL=...`).
   - Zero-config automatic fallback to high-performance local **SQLite** (`storage/overlord.db`), ensuring instant out-of-the-box readiness.

6. **Tactical Mission Scenario Simulator & Alert Center**:
   - Real-time scenario injection buttons:
     - `❤️ Simulate Life-Sign (Survivor)`
     - `⚠️ Simulate Casualty (Deadbody)`
     - `⚡ Simulate Geofence Breach`
     - `🪫 Low Battery Emergency RTL (12%)`
     - `📻 Video RF Jamming & Noise`
     - `📡 LoRa Packet Burst Test`
   - Real-time Web Audio API tactical sound synthesis (positive target chime, caution tone, critical breach warble).

---

## Quickstart (One-Click Launch)

### Linux / macOS
```bash
./run.sh
```
*(Automatically creates `.venv`, installs all dependencies from `requirements.txt`, and starts the server).*

### Windows
Double-click `run.bat` or run from Command Prompt:
```cmd
run.bat
```
*(Automatically creates `.venv`, installs dependencies, launches the server, and opens `http://localhost:8000` in your browser).*

---

## Directory Structure

```
/overlord/
├── app/
│   ├── config.py                 # Central configurations & environment variables
│   ├── database.py               # Multi-engine DB layer (PostgreSQL / SQLite fallback)
│   ├── models.py                 # Pydantic schemas & SQLAlchemy ORM models
│   ├── services/
│   │   ├── video_streamer.py     # Live MJPEG stream with HUD, scanlines, and noise
│   │   ├── geofence_planner.py   # Polygon geometry & boustrophedon lawnmower path planner
│   │   ├── lora_service.py       # LoRa packet reassembly & radio telemetry
│   │   └── simulator.py          # UAV/UGV kinematics, waypoint follower, scenarios
│   └── routers/
│       ├── telemetry.py          # WebSocket (5Hz) & REST telemetry endpoints
│       ├── video.py              # MJPEG streaming endpoints
│       ├── geofence.py           # Geofence CRUD & mission dispatch
│       ├── detections.py         # AI detection storage & snapshot viewer
│       ├── lora.py               # LoRa packet rx & status
│       └── simulation.py         # Scenario injections & drone controls
├── static/
│   ├── css/dashboard.css         # Tactical defense C2 styling & layer switcher
│   └── js/
│       ├── map.js                # Leaflet satellite map, polygon draw, waypoints
│       ├── telemetry.js          # WebSocket listener & Web Audio synthesizer
│       ├── detections.js         # Snapshot gallery & modal inspector
│       └── app.js                # Application bootstrapper & event binder
├── templates/
│   └── index.html                # Single-page Tactical C2 Dashboard
├── storage/
│   └── snapshots/                # Stored detection snapshots
├── main.py                       # FastAPI entrypoint & server lifespan
├── requirements.txt              # Frozen Python dependencies
├── run.sh                        # One-click startup script (Linux/macOS)
├── run.bat                       # One-click startup script (Windows)
└── README.md
```

---

## API Endpoints Overview
- `GET /`: Tactical C2 Web Dashboard
- `GET /health`: System health and active links
- `GET /api/stream/uav`: Live UAV MJPEG analog video stream
- `GET /api/stream/ugv`: Live UGV MJPEG optical ground stream
- `WS /api/telemetry/ws`: Real-time bi-directional telemetry and alert stream
- `POST /api/geofence/generate-path`: Calculates lawnmower search waypoints
- `POST /api/geofence/upload`: Dispatches autonomous mission to drone autopilot
- `POST /api/simulation/trigger`: Injects tactical scenarios (`LIFE_SIGN`, `CASUALTY`, `BREACH`, etc.)
- `POST /api/lora/rx`: Ingests raw LoRa packets from physical transceiver hardware
- `GET /api/snapshots/{id}`: Returns high-res detection snapshot JPEG
