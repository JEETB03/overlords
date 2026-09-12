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

---

## API Endpoints & Architecture Overview

The system features interactive OpenAPI Swagger documentation accessible at **`http://localhost:8000/docs`** and ReDoc at **`http://localhost:8000/redoc`**.

### 1. External LoRa Link RX Station API (`http://172.16.59.210:8000`)
The tactical dashboard integrates with an external LoRa RX ground station that receives progressive image packets transmitted over long-range radio:

| Remote Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | RX station status, storage root (`E:\HH4.0\docs\received`), and state file check. |
| `/missions` | `GET` | Lists completed survey missions with query params `limit` (int, default 50) and `order` (`desc` or `asc`). |
| `/missions/latest` | `GET` | Returns full detail and telemetry of the most recently reassembled aerial mission. |
| `/missions/{mission_id}` | `GET` | Detailed metadata and file download paths for a specific mission ID. |
| `/missions/{mission_id}/metadata` | `GET` | Raw JSON telemetry payload (lat/lon coordinates, camera type, operator, drone ID). |
| `/missions/{mission_id}/image` | `GET` | Binary JPEG/PNG byte stream of the reconstructed aerial survey snapshot. |

### 2. Local Tactical C2 & LoRa Link Proxy Endpoints (`/api/lora-link`)
The C2 dashboard runs an autonomous background synchronization service (`app/services/lora_link_service.py`) that polls the hardware RX ground station, downloads reconstructed imagery to local storage (`storage/snapshots/`), ingests mission telemetry into the database, and renders the sequential reconnaissance corridor:

- `GET /api/lora-link/status`: Connectivity state, sync count, base URL, and health diagnostics.
- `GET /api/lora-link/missions`: Lists downlinked missions (`limit: int = 50`, `order: str = "desc"`).
- `GET /api/lora-link/missions/latest`: Most recently completed survey mission with embedded telemetry.
- `GET /api/lora-link/missions/{mission_id}`: Full mission details, image size, and coordinate metadata.
- `GET /api/lora-link/missions/{mission_id}/metadata`: Raw metadata JSON payload.
- `GET /api/lora-link/track`: Returns chronologically ordered GPS flight corridor waypoints (`M1`, `M2`, `M3`, ...) for mapping the UAV trajectory.
- `GET /api/lora-link/image/{mission_id}`: High-resolution reconstructed survey photo (cached locally with fallback to remote download).
- `POST /api/lora-link/sync`: Manually triggers an immediate pull from the RX ground station and broadcasts WebSocket tactical alerts.

### 3. Core Tactical C2 Endpoints
- `GET /`: Tactical Command and Control Web Dashboard UI.
- `GET /health`: C2 system health, active database type (PostgreSQL / SQLite fallback), and fleet operational modes.
- `GET /api/stream/uav`: Live UAV FLIR IR thermal analog video stream (MJPEG with dynamic HUD pitch ladder and RF noise).
- `GET /api/stream/ugv`: Live UGV optical rover video stream with LiDAR collision alerts.
- `WS /api/telemetry/ws`: High-rate (5Hz) bi-directional WebSocket telemetry stream for coordinates, compass heading, battery voltage, and mission alerts.
- `POST /api/geofence/generate-path`: Computes boustrophedon (lawnmower) autonomous search waypoints and estimated flight duration.
- `POST /api/geofence/upload`: Uploads planned polygon waypoints directly to the UAV autopilot.
- `GET /api/detections`: Lists all target detections with filtering (`ALL`, `LORA_MISSION`, `SURVIVOR`, `CASUALTY`).
- `GET /api/snapshots/{id}`: Returns JPEG image bytes for any AI detection or LoRa Link mission.
- `POST /api/simulation/trigger`: Injects tactical training events (`LIFE_SIGN`, `CASUALTY`, `GEOFENCE_BREACH`, `LOW_BATTERY`).
- `POST /api/lora/rx`: Ingests raw serial radio packet chunks from physical SX1262 transceiver hardware.

---

## Active LoRa Link Reconnaissance Missions

| Waypoint | Mission ID | Coordinates | Camera | Status | Resolution | Size |
|---|---|---|---|---|---|---|
| **M1** | `LL-20260913-005138-6F8E` | `22.572600°N, 88.363900°E` | RunCam | Cached | 1024x1024 | 111 KB |
| **M2** | `LL-20260912-235309-8E38` | `22.572600°N, 88.363900°E` | RunCam | Cached | 877x620 | 69 KB |
| **M3** | `LL-20260913-025254-78E4` | `22.560047°N, 88.355082°E` | RunCam | Cached | 1024x1024 | 82 KB |
| **M4** | `LL-20260913-025953-11E1` | `22.584270°N, 88.362341°E` | RunCam | Cached | 1024x1024 | 97 KB |

*The dashboard draws an interconnected cyan flight corridor connecting waypoints M1 through M4, providing instant visual confirmation of autonomous survey coverage.*

