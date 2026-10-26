# NagarX — 3D Urban Digital Twin & Disaster-Aware Route-Planning Prototype

NagarX is an interactive 3D urban digital-twin and topological route-planning research prototype built with **Next.js (App Router), React, TypeScript, CesiumJS, Zustand, FastAPI, NetworkX, Shapely, and PostgreSQL/PostGIS**.

It is designed around a focused spatial engineering research question:

> **When a road corridor or urban area becomes affected by a simulated disaster, how does the available route between two locations change?**

---

## Core Capabilities

1. **Mission Overview Workspace (`/`)**
   - Summarizes the active study area, topological graph size, configured hazard scenario, backend readiness, and active data provenance (`Demo Mode` vs `Live PostGIS`).
   - Provides one-click entry to **Start Route Analysis**, **Run Demonstration Flood Scenario**, or **Reset Demo**.

2. **3D City & Route Workspace (`/workspace`)**
   - Renders the study area road hierarchy, waterways, 3D building footprints, landmarks, simulated hazard footprints, affected road segments, **Baseline Route** (dashed blue), and **Hazard-Aware Alternative Route** (solid glowing orange) on a client-only **CesiumJS 3D globe**.
   - Includes a compact top navigation bar, collapsible left 7-step workflow panel, collapsible right comparison & limitations panel, bottom-left map symbol legend, quick layer controls, and camera framing (`Area` / `Fit Route`).
   - Retains optional floating-window urban-planning modules (`Layer Manager`, `Feature Inspector`, `Site Suitability`, `Road & Zoning Proposals`, `Parametric Exposure Sim`, `Station Dispatch`, `Scenario Comparison`, `Spatial AI Assistant`) under **Tools ▾** without cluttering the map by default.

3. **Scenario Builder (Simulated Hazards)**
   - Supports **Flood**, **Fire**, **Road Blockage**, and **Generic Affected Zone** simulations.
   - Defines hazards via **interactive 3D map polygon drawing** (validated for $\ge 3$ non-collinear, non-self-intersecting vertices), **circular radius zones**, and/or **explicit street/bridge segment selection**.
   - Supports two documented graph-cost rules:
     - **Impassable (`closed`)**: Affected directed edges are excluded from the hazard-aware graph.
     - **Traversal Penalty (`penalized`)**: Affected directed edges remain traversable with a user-defined cost multiplier $k \ge 1.0$.

4. **Topological Shortest-Path Routing & Comparison**
   - Uses **Dijkstra's shortest-path algorithm** over planarized road intersections (nodes) and directed navigable street segments (edges) using identical origin, destination, and base network topology for both baseline and hazard-aware calculations.
   - Reports route feasibility, total distance, nominal free-flow travel time (from OSM `maxspeed` or road-class defaults), traversed graph segments, affected segments encountered, cumulative **simulated affected-segment exposure (m)**, measured computation time, plain-English detour explanation, and explicit model assumptions/limitations.
   - Reports **"No feasible route found under the current scenario"** whenever closed edges sever all paths between origin and destination.

---

## Data Sources, Provenance & Modes

NagarX strictly separates **Live PostGIS Mode** and **Offline Demo Mode** and displays the active mode in the top navigation bar and on every analysis result:

| Mode / Dataset | Location in Repo | Nature & Provenance | Routing Role |
|---|---|---|---|
| **Live PostGIS Mode** (`live`) | `db/schema.sql`, `etl/ingest_osm.py`, `POST /api/v1/emergency/route-compare` | PostgreSQL/PostGIS spatial tables (`roads`, `buildings`, `facilities`, `parcels`) projected to UTM Zone 43N (`EPSG:32643`). | Server-side planarized `NetworkX` Dijkstra routing. Fails honestly if PostGIS is unreachable (never silently fakes a live result). |
| **New Panvel — Kalundre River Corridor** (`demo`) | `frontend/public/data/panvel-osm-demo.json` (built via `scripts/build_demo_network.py` from `db/cache/` & `cache/`) | Authentic cached **OpenStreetMap Overpass extract** covering New Panvel / Adivali-Devad (`73.119°E–73.194°E, 18.982°N–19.024°N`): 279 connected ways, 2,219 nodes, Kalundre River, 26 medical/emergency facilities, 450 building footprints. | Client-side deterministic binary-heap Dijkstra routing when running without PostGIS. |
| **Controlled Synthetic Benchmark Grid** (`demo`) | `frontend/lib/routing-engine.ts` (`pilot_synthetic_grid`) | Explicitly labelled synthetic 7×7 arterial/sub-arterial lattice (49 intersections, 168 directed links). | Analytical verification testbed for shortest-path and penalty behavior. |
| **Regional Reference Overlays** | `frontend/public/data/{india-states,india-highways,pune-waterbodies}.json` | Simplified GeoJSON state boundaries, inter-city national highways, and Pune river/reservoir hydrography. | Visual cartographic context layers on the 3D globe only (not street-level routing graphs). |

---

## Repository Structure

```text
urban-digital-twin/
├── frontend/                     # Next.js 15 (App Router) + React 19 + TypeScript + CesiumJS
│   ├── app/                      # '/' (Overview), '/workspace' (3D Workspace), '/api/v1/[...path]' proxy
│   ├── cesium/                   # Client-only CesiumViewer, mapBridge, routeAnalysisLayer, live/region loaders
│   ├── components/
│   │   ├── overview/             # MissionOverview entry workspace
│   │   ├── route-workspace/      # RouteWorkflowPanel (7 steps + Scenario Builder), RouteResultsPanel, MapOverlayControls
│   │   ├── layout/               # TopNavbar, Workspace shell, WindowManager, Taskbar, CommandPalette
│   │   └── panels/               # Optional floating urban-planning & diagnostic panels
│   ├── lib/                      # Deterministic routing-engine.ts (planarizer + Dijkstra), API client, constants
│   ├── stores/                   # Zustand state (route-analysis-store + map/layer/scenario/window stores)
│   ├── public/data/              # panvel-osm-demo.json + regional GeoJSON reference layers
│   └── tests/                    # Automated TypeScript routing, store workflow, and API contract tests
├── backend/                      # FastAPI spatial backend
│   ├── app/api/v1/routers/       # REST routers (/ready, /city, /layers, /scenarios, /emergency/route-compare, ...)
│   ├── app/engines/network/      # graph_builder.py, routing.py, emergency_routing.py, disaster_routing.py
│   ├── app/services/             # Orchestration services (EmergencyService.compare_od_routes, ...)
│   └── tests/                    # Pytest unit, API contract, and PostGIS integration tests
├── db/                           # PostGIS schema.sql and cached Overpass extracts
├── etl/                          # OpenStreetMap -> PostGIS ingestion pipeline
└── scripts/build_demo_network.py # Deterministic builder for frontend/public/data/panvel-osm-demo.json
```

---

## Setup & Running Locally

### 1. Run Frontend Immediately (Zero External Keys Required — Offline Demo Mode)

```bash
cd frontend
npm install          # Installs packages & copies Cesium static workers/assets to public/cesium
npm run dev          # Starts Next.js on http://0.0.0.0:3000
```

- Open `http://localhost:3000` for the **Mission Overview**, or `http://localhost:3000/workspace` for the **3D City Workspace**.
- No Cesium Ion token or external routing key is required; Cesium uses OpenStreetMap/CARTO dark basemap tiles and local WebGL rendering, and Demo Mode uses the bundled OpenStreetMap graph.

### 2. Optional: Run Full Live Backend (FastAPI + PostGIS)

1. Copy `.env.example` to `.env` and start PostGIS:
   ```bash
   cp -n .env.example .env
   docker compose up -d db
   ```
2. Install backend dependencies and seed/ingest OSM data (if initializing a fresh DB):
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r backend/requirements.txt
   .venv/bin/python db/seed_demo.py
   ```
3. Start the FastAPI server:
   ```bash
   cd backend
   ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Next.js automatically proxies `/api/v1/*` requests to `BACKEND_ORIGIN` (defaults to `http://127.0.0.1:8000`). Once `/api/v1/ready` reports `ready: true`, NagarX unlocks **Live PostGIS** execution.

### Environment Variables (`frontend/.env.local`, all optional)

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_ORIGIN` | `http://127.0.0.1:8000` | Server-side proxy target used by `app/api/v1/[...path]/route.ts`. |
| `NEXT_PUBLIC_API_BASE_URL` | `/api/v1` | Browser API prefix (keep `/api/v1` so requests traverse the Next.js proxy). |
| `NEXT_PUBLIC_CESIUM_ION_TOKEN` | *(empty)* | Optional Cesium Ion token for terrain/imagery upgrades. |
| `NEXT_PUBLIC_BACKEND_REQUIRED` | `false` | Set to `true` to disable automatic offline Demo Mode initialization. |

---

## Verification, Testing & Production Build

```bash
# Frontend TypeScript check, ESLint, automated tests, and production build
cd frontend
npx tsc --noEmit
npm run lint
npm test
npm run build

# Backend unit & API contract tests
cd ../backend
../.venv/bin/pytest tests/ -v
```

---

## Known Assumptions & Limitations

- **Simulated Hazards Only**: All flood polygons, fire cordons, road blockages, and penalty zones are user-configured or preset geometric simulations for route-planning research — never live emergency alerts or physical hydrodynamic/fire-spread model outputs.
- **Nominal Travel-Time Model**: Travel times use OSM `maxspeed` tags where available and standard speed-by-road-class defaults (`motorway` 80, `primary` 50, `secondary` 40, `tertiary` 35, `residential` 25 km/h) without live traffic congestion or turn-signal delays.
- **Graph Coverage**: Routing operates strictly over connected road ways in the loaded dataset; unmapped private alleys, informal footpaths, and field-level debris are outside the graph.
- **Terminology & Safety**: A feasible *hazard-aware alternative* indicates graph connectivity outside closed segments or lower penalized cost; it does **not** certify real-world physical life safety.
