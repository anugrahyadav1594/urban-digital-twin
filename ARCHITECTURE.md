# NagarX System Architecture

## 1. Architectural Overview

NagarX separates 3D cartographic rendering, deterministic client/server topological routing, and database persistence into explicit layers:

1. **Presentation & 3D Geospatial Canvas (`frontend/`)**
   - **Next.js 15 App Router** serves `/` (`MissionOverview`) and `/workspace` (`3D City Workspace`).
   - **CesiumJS (`frontend/cesium/`)** is loaded exclusively on the client (`dynamic(..., { ssr: false })` + static worker assets copied to `frontend/public/cesium` by `scripts/copy-cesium.mjs`). React components communicate with Cesium through a typed imperative bridge (`cesium/map-bridge.ts`) and declarative store subscribers (`cesium/routeAnalysisLayer.ts`).
   - **Unified Workflow State (`frontend/stores/route-analysis-store.ts`)** manages study area selection, waypoints, scenario builder drafts, map interaction modes, topological affected-segment previews, async request cancellation, input-signature staleness tracking, and route comparison results.

2. **Next.js Server-Side API Proxy (`frontend/app/api/v1/[...path]/route.ts`)**
   - Forwards browser `/api/v1/*` requests to `BACKEND_ORIGIN` (`http://127.0.0.1:8000` by default) so browser code never hardcodes `localhost` ports or leaks server-side configuration.

3. **Spatial Backend & Engines (`backend/app/`)**
   - **FastAPI Routers (`app/api/v1/routers/`)** validate requests with Pydantic and map domain errors cleanly to HTTP status codes (`422` validation error, `409` missing spatial data, `503` PostGIS unavailable).
   - **Pure Spatial Engines (`app/engines/`)** operate in projected metric coordinates (`EPSG:32643` UTM Zone 43N) using `Shapely` and `NetworkX`, isolated from SQLAlchemy ORM sessions.
   - **PostGIS Persistence (`app/repositories/` & `db/schema.sql`)** stores versioned spatial entities (`roads`, `buildings`, `parcels`, `facilities`, `scenarios`, `analysis_results`).

---

## 2. Topological Graph & Hazard-Cost Model

Both the backend engine (`backend/app/engines/network/disaster_routing.py`) and the local Demo Mode engine (`frontend/lib/routing-engine.ts`) implement the same mathematical routing formulation:

- **Nodes ($V$)**: Road intersections and segment vertices, planarized at interior crossings and filtered to the largest strongly connected component (`routable_core`) so isolated boundary fragments cannot trap waypoint snapping.
- **Directed Edges ($E$)**: Navigable street segments $(u, v)$ carrying geodesic/projected length $\ell_e > 0$ (m), speed $v_e > 0$ (km/h), and nominal traversal time $t_e = \ell_e / (v_e / 3.6)$ (s). One-way tags emit a single directed arc; bidirectional streets emit $(u, v)$ and $(v, u)$.
- **Hazard Classification**:
  - Given an active scenario $S$ with optional polygon/buffer $P_S$ and explicit segment sets $R_{\text{affected}}, R_{\text{slowed}}$, an edge $e \in E$ is marked affected if $\text{geom}(e) \cap P_S \neq \emptyset$ or $\text{road\_id}(e) \in R_{\text{affected}}$.
  - In **Impassable (`closed`)** mode, affected edges $E_{\text{closed}}$ are removed: $E' = E \setminus E_{\text{closed}}$.
  - In **Penalized (`penalized`)** mode with multiplier $k \ge 1.0$, affected edges remain in $E'$ with modified weight $w'_e = k \cdot w_e$.
- **Comparison Invariant**:
  - Both the **Baseline Route** and **Hazard-Aware Alternative Route** run **Dijkstra's shortest-path algorithm** between the **identical snapped origin node $s \in V$ and destination node $t \in V$** over the same base graph $G = (V, E)$.
  - **Simulated Affected-Segment Exposure** for any path $\pi$ is defined explicitly as:
    $$\text{Exposure}(\pi) = \sum_{e \in \pi \cap (E_{\text{closed}} \cup E_{\text{penalized}})} \ell_e \quad (\text{metres})$$

---

## 3. Point-to-Point Route Comparison API Contract

### `POST /api/v1/emergency/route-compare`

**Request Body:**
```json
{
  "origin": { "lon": 73.11907, "lat": 18.99672, "label": "New Panvel Fire Brigade" },
  "destination": { "lon": 73.13008, "lat": 18.98628, "label": "Life Care Hospital" },
  "scenario": {
    "name": "Demonstration Flood — Kalundre River Lower Bridge",
    "type": "flood",
    "active": true,
    "severity_mode": "closed",
    "penalty_multiplier": 3.0,
    "polygon": [[73.1279, 18.9866], [73.1299, 18.9866], [73.1299, 18.9882], [73.1279, 18.9882]],
    "center": null,
    "radius_m": null,
    "affected_road_ids": ["osm_way_459498364"],
    "slowed_road_ids": []
  },
  "cost_metric": "time"
}
```

**Response Body (`200 OK`):**
- `baseline_route`: `{ feasible, path, distance_m, travel_time_s, segment_count, affected_segment_count, affected_road_ids, exposed_distance_m, snap_origin_m, snap_destination_m }`
- `hazard_aware_route`: identical schema (`feasible: false`, `path: []` if disconnected)
- `affected_network`: `{ closed_edge_count, penalized_edge_count, closed_road_ids, penalized_road_ids, closed_segments, penalized_segments }`
- `comparison`: `{ baseline_feasible, alternative_feasible, routes_identical, distance_delta_m, distance_delta_pct, time_delta_s, time_delta_pct, avoided_segments, exposure_reduction_m, summary, assumptions, limitations, warnings }`
- `computation_time_ms`: measured server execution time in ms
- `provenance`: `{ data_mode: "live_postgis", execution_engine: "backend_networkx_dijkstra", algorithm, dataset_version, analysis_srid, cost_metric }`

---

## 4. Strict Separation of Live vs Demo Execution

- On startup, the client probes `GET /api/v1/ready`.
- If PostGIS is reachable (`200 OK`), `Live PostGIS` mode is enabled; otherwise the workspace operates in `Demo Mode` with a persistent header indicator (`DEMO MODE · SIMULATED`).
- If the user runs an analysis in `Live PostGIS` mode and the API fails, times out, or returns `503`, NagarX surfaces the error directly and offers explicit **Retry Live API** or **Switch to Demo Mode & Run** actions — it never silently substitutes demo output as a live database result.
