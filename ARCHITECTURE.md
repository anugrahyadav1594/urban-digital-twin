# NAGAR-X — System Architecture

## 1. Purpose

NAGAR-X is an AI-assisted urban planning and digital-twin platform designed to let planners explore a 3D representation of an urban area, inspect spatial layers, create and evaluate planning scenarios, run analytical workflows, and receive structured AI-assisted recommendations.

The architecture separates **visual interaction**, **application/API logic**, **geospatial data**, **deterministic analysis**, and **AI interpretation** into distinct layers.

The primary architectural principle is:

> **The frontend owns interaction and visualization; the backend owns authoritative planning logic, geospatial processing, analysis, persistence, and orchestration.**

---

## 2. High-Level Architecture

```text
                              ┌──────────────────────┐
                              │        PLANNER       │
                              │   / Decision Maker   │
                              └──────────┬───────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                              │
│                                                                     │
│  Next.js + React + TypeScript + CesiumJS + Zustand                  │
│                                                                     │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐   │
│  │ Horizontal   │  │ Floating      │  │ CesiumJS 3D Digital     │   │
│  │ Navbar       │  │ Tool Windows  │  │ Twin / Map Canvas       │   │
│  └──────────────┘  └───────────────┘  └─────────────────────────┘   │
│                                                                     │
│  Layers • Planning • Analysis • Scenario • Simulation • Compare     │
│  AI • Selection • Results • Workspace State                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ REST / JSON / GeoJSON
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND API LAYER                           │
│                                                                     │
│                         FastAPI /api/v1                             │
│                                                                     │
│  Routers → DTOs → Services → Engines / Agents → Storage             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
              ▼                ▼                 ▼
┌────────────────────┐ ┌─────────────────┐ ┌────────────────────────┐
│  GEOSPATIAL /      │ │   AI PLANNING   │ │   SCENARIO / ANALYSIS  │
│  ANALYSIS ENGINES  │ │   ORCHESTRATOR  │ │   SERVICES & ENGINES   │
│                    │ │                 │ │                        │
│ GIS / Network /    │ │ Planner         │ │ Scenario management    │
│ Spatial metrics    │ │ GIS Agent       │ │ Comparison             │
│ Site scoring       │ │ Cost Agent      │ │ Accessibility          │
│ Travel time        │ │ Risk Agent      │ │ Emergency              │
│ Constraints        │ │ Critic Agent    │ │ Network resilience     │
│ Optimization       │ │ Report Agent    │ │ Facility location      │
└──────────┬─────────┘ └────────┬────────┘ └───────────┬────────────┘
           │                    │                      │
           └────────────────────┼──────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                              │
│                                                                     │
│                     PostgreSQL + PostGIS                            │
│                                                                     │
│  Urban Features • Scenarios • Results • Spatial Data • Metadata     │
└─────────────────────────────────────────────────────────────────────┘

                     ▲
                     │ ETL / ingestion
                     │
             ┌───────┴────────┐
             │ OpenStreetMap  │
             │ / Geo Data     │
             └────────────────┘
```

---

## 3. Architectural Layers

NAGAR-X is organized into the following logical layers:

1. **Presentation and Visualization Layer**
2. **Frontend State and Interaction Layer**
3. **API Layer**
4. **Application / Service Layer**
5. **Analysis and Optimization Layer**
6. **AI Orchestration Layer**
7. **Persistence Layer**
8. **Geospatial ETL Layer**

Each layer has a distinct responsibility and communicates through defined interfaces.

---

# 4. Frontend Architecture

## 4.1 Technology

The frontend is built with:

- Next.js
- React
- TypeScript
- CesiumJS
- Zustand

The application is structured as a full-viewport geospatial workspace rather than a traditional dashboard with a permanent sidebar.

The primary visual surface is the CesiumJS canvas. Planning tools appear as floating windows above the map.

## 4.2 Frontend Responsibilities

The frontend is responsible for:

- Rendering the 3D digital twin
- Rendering map and geographic layers
- Camera navigation
- Spatial picking and selection
- User interaction
- Drawing and visual editing
- Scenario interaction
- Floating-window management
- Workspace layout
- Client-side state management
- Displaying analysis results
- Displaying job/progress state
- Visualizing proposed infrastructure
- Calling backend APIs

The frontend should **not** become the source of truth for authoritative planning calculations.

## 4.3 Frontend Structure

```text
frontend/
│
├── app/
│   ├── workspace/
│   └── ...
│
├── cesium/
│   ├── CesiumViewer.tsx
│   └── map-bridge.ts
│
├── components/
│   ├── layout/
│   ├── windows/
│   ├── panels/
│   └── ui/
│
├── stores/
│   ├── window store
│   ├── map store
│   ├── layer store
│   ├── selection store
│   ├── scenario store
│   ├── analysis store
│   ├── job store
│   └── AI store
│
├── lib/
│   ├── API client
│   ├── city model
│   ├── mock engine
│   └── constants
│
├── public/
│   └── data/
│
├── scripts/
└── types/
```

---

# 5. CesiumJS Architecture

## 5.1 Viewer

`CesiumViewer.tsx` provides the main 3D visualization surface.

The viewer is responsible for:

- Initializing Cesium
- Loading imagery and terrain providers
- Managing camera state
- Rendering geographic layers
- Handling spatial picking
- Displaying GeoJSON and planning proposals
- Supporting navigation and map interaction

## 5.2 Map Bridge

`map-bridge.ts` provides an imperative bridge between React application state and the Cesium viewer.

This prevents the application from coupling every UI component directly to Cesium's imperative APIs.

Conceptually:

```text
React / Zustand
      │
      ▼
 Map Bridge
      │
      ▼
Cesium Viewer
      │
      ▼
3D Scene
```

---

# 6. Floating Window Architecture

The workspace uses a floating-window system for planning tools.

```text
Workspace
   │
   ├── Top Navbar
   │
   ├── Cesium Canvas
   │
   ├── Floating Window Manager
   │       │
   │       ├── City
   │       ├── Layers
   │       ├── Planning
   │       ├── Analysis
   │       ├── Scenario
   │       ├── Simulation
   │       ├── Compare
   │       └── AI
   │
   └── Taskbar
```

Each window has independent:

- Position
- Size
- Visibility
- Focus state
- Minimized/maximized state
- Z-index

The window manager provides:

- Dragging
- Resizing
- Snapping
- Maximizing
- Restoring
- Closing
- Automatic alignment

---

# 7. Frontend State Architecture

Zustand is used for application state.

State is separated by domain rather than placing the complete application state in a single store.

```text
                    ┌───────────────┐
                    │ Zustand State │
                    └───────┬───────┘
                            │
       ┌────────┬───────────┼───────────┬──────────┐
       ▼        ▼           ▼           ▼          ▼
    Window    Map         Layers     Selection   Scenario
       │        │           │           │          │
       └────────┴───────────┼───────────┴──────────┘
                            │
                    Analysis / Jobs / AI
```

This keeps UI state, map state, scenario state, and asynchronous analysis state independently manageable.

---

# 8. Backend Architecture

The backend is implemented using FastAPI.

The backend is responsible for authoritative application behavior and computational workflows.

```text
backend/
│
└── app/
    ├── agents/
    │   ├── planning_agent.py
    │   ├── gis_agent.py
    │   ├── cost_agent.py
    │   ├── risk_agent.py
    │   ├── critic_agent.py
    │   ├── report_agent.py
    │   ├── llm_client.py
    │   ├── orchestrator.py
    │   └── tools.py
    │
    ├── api/
    │   └── v1/
    │
    ├── core/
    │
    └── storage/
```

The backend follows a layered request flow:

```text
HTTP Request
     │
     ▼
FastAPI Router
     │
     ▼
Validation / DTO
     │
     ▼
Service
     │
     ├──────────────► Analysis Engine
     ├──────────────► Optimization Engine
     ├──────────────► AI Orchestrator
     └──────────────► Storage
     │
     ▼
Response DTO
     │
     ▼
Frontend
```

---

# 9. API Architecture

The API is versioned under:

```text
/api/v1
```

The backend exposes domain-oriented routes for:

- Scenarios
- Scenario changes
- Scenario comparison
- Planning / road analysis
- Accessibility analysis
- Emergency analysis
- Risk / network resilience analysis
- AI planning
- Facility-location optimization
- Job/result handling

The API uses JSON for standard application data and GeoJSON where spatial geometry is exchanged.

---

# 10. Scenario Architecture

Scenarios represent alternative planning states that can be created, modified, analyzed, and compared.

```text
Base City Model
      │
      ▼
  Scenario A ───────┐
                    │
  Scenario B ───────┼──► Comparison Engine
                    │          │
  Scenario C ───────┘          ▼
                         Ranked Results
```

Scenario operations include:

- Create scenario
- Retrieve scenario
- Update scenario
- Apply scenario changes
- Compare multiple scenarios

The backend remains the authoritative source for scenario persistence and comparison results.

---

# 11. Analysis Architecture

Analysis functionality is exposed as domain-specific backend operations.

Current analysis domains include:

### Accessibility

Evaluates spatial accessibility and catchment-related metrics.

### Emergency

Evaluates emergency-response-related spatial/network conditions.

### Risk / Network Resilience

Evaluates network resilience and risk-related metrics.

### Road Planning

Accepts spatial road proposals and processes them for analysis and visualization.

### Facility Location

Provides optimization-oriented facility-location analysis.

The architecture allows additional analysis engines to be added without changing the Cesium visualization layer.

---

# 12. AI Architecture

AI functionality is intentionally separated from deterministic analysis.

The central component is:

```text
backend/app/agents/orchestrator.py
```

The orchestrator coordinates specialized agents and deterministic tools.

```text
                         User Request
                              │
                              ▼
                      PlanningAgent
                              │
                              ▼
                       Planning Intent
                              │
                              ▼
                 Deterministic Tool Layer
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     Population          Travel Time        Constraints
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                    Site Score / Cost
                              │
                              ▼
                 Specialized AI Agents
                    │       │       │
                    ▼       ▼       ▼
                   GIS     Cost    Risk
                    │       │       │
                    └───────┼───────┘
                            ▼
                     CriticAgent
                            │
                            ▼
                     ReportAgent
                            │
                            ▼
                    Structured Result
```

### AI Agents

- `PlanningAgent` — extracts structured planning intent.
- `GISAgent` — interprets spatial analysis.
- `CostAgent` — interprets cost-related outputs.
- `RiskAgent` — interprets risk and resilience outputs.
- `CriticAgent` — validates consistency.
- `ReportAgent` — synthesizes the final report.
- `LLMClient` — provides the LLM integration boundary.

---

# 13. AI vs Deterministic Computation

NAGAR-X deliberately avoids using an LLM as the sole computational authority for spatial planning.

```text
                 Planning Question
                        │
                        ▼
                 LLM / AI Layer
                        │
              Intent + Interpretation
                        │
                        ▼
              Deterministic Engines
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
     Spatial          Network          Cost /
     Analysis         Analysis        Constraints
       │                │                │
       └────────────────┼────────────────┘
                        ▼
                 Validation Layer
                        │
                        ▼
                 AI Report Layer
```

This provides a clear boundary between:

- **What the system calculates**
- **What the AI interprets**
- **What the user ultimately sees**

---

# 14. Data Architecture

PostgreSQL with PostGIS acts as the persistent geospatial data layer.

```text
                  External Sources
                        │
                        ▼
                   ETL Pipeline
                        │
                        ▼
               PostgreSQL + PostGIS
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Urban Data     Scenarios      Metadata
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                  Backend Services
                        │
                        ▼
                    Frontend
```

PostGIS is used for authoritative spatial persistence and spatial querying.

---

# 15. Coordinate Reference Systems

The project uses separate coordinate reference systems for geographic storage and metric analysis.

| Purpose | CRS |
| --- | --- |
| Storage | `EPSG:4326` |
| Analysis | `EPSG:32643` |

`EPSG:4326` is used for geographic coordinate storage and interoperability.

`EPSG:32643` provides projected metric coordinates for analysis in the documented pilot region.

---

# 16. ETL Architecture

The ETL pipeline provides the bridge between external geospatial data and the internal urban model.

```text
OpenStreetMap / External Data
             │
             ▼
        Data Retrieval
             │
             ▼
       GeoData Processing
             │
      ┌──────┴──────┐
      ▼             ▼
 Geometry        Attributes
 Validation      Validation
      │             │
      └──────┬──────┘
             ▼
        CRS Handling
             │
             ▼
        PostGIS Storage
```

The pipeline is designed to preserve real-data provenance and expose ingestion failures rather than silently replacing missing source data.

---

# 17. Frontend–Backend Data Flow

A typical planning interaction follows:

```text
1. User opens Planning window
             │
             ▼
2. User defines planning requirement
             │
             ▼
3. Frontend validates UI input
             │
             ▼
4. Frontend sends API request
             │
             ▼
5. Backend router receives request
             │
             ▼
6. Service / engine performs analysis
             │
             ▼
7. Data retrieved from PostGIS
             │
             ▼
8. Analysis / optimization executes
             │
             ▼
9. Result returned as DTO / GeoJSON
             │
             ▼
10. Zustand updates application state
             │
             ▼
11. Cesium / panels render result
```

For AI planning, the analysis stage additionally includes the agent orchestration pipeline.

---

# 18. Visualization Data Flow

```text
PostGIS / Backend
       │
       ▼
 API / GeoJSON / Result DTO
       │
       ▼
 Frontend API Client
       │
       ▼
 Zustand / Application State
       │
       ▼
 Map Bridge
       │
       ▼
 CesiumJS
       │
       ▼
 3D Visualization
```

Cesium remains primarily a visualization and interaction layer.

---

# 19. Error and Failure Boundaries

### Frontend Failure

The UI should surface recoverable API or visualization failures without crashing the complete workspace.

### API Failure

The FastAPI layer converts application failures into structured HTTP responses.

### Database Failure

Database connectivity and PostGIS availability are checked through backend diagnostics. Database-dependent operations should fail explicitly rather than produce misleading spatial results.

### ETL Failure

ETL failures should be reported at the data/layer level. External data retrieval failures must not silently become synthetic production data.

### AI Failure

AI interpretation should not replace missing deterministic facts. The system should distinguish between calculated values and AI-generated interpretation.

---

# 20. Security Boundaries

Sensitive configuration belongs outside source-controlled code.

Examples include:

- Database credentials
- Cesium Ion tokens
- LLM/API credentials
- Deployment secrets

Environment files are used for local configuration.

The frontend should only expose variables explicitly intended for browser use, such as `NEXT_PUBLIC_*` values.

Server-side secrets must remain in the backend environment.

---

# 21. Deployment Model

The local development architecture uses Docker Compose for the database and independent development processes for frontend and backend.

```text
Developer Machine
│
├── Next.js / React / CesiumJS
│        :3000
│
├── FastAPI
│        :8000
│
└── Docker Compose
         │
         └── PostgreSQL + PostGIS
                  :5432
```

A production deployment can preserve the same logical boundaries while replacing local development services with managed or containerized infrastructure.

---

# 22. Workspace Operating Model

The product workflow is designed around an urban-planning loop:

```text
OBSERVE
   ↓
DESIGN
   ↓
EVALUATE
   ↓
SIMULATE
   ↓
COMPARE
   ↓
RECOMMEND
   ↓
OBSERVE / ITERATE
```

### Observe

Inspect the existing urban environment and available spatial layers.

### Design

Create or modify a planning proposal or scenario.

### Evaluate

Run spatial, accessibility, risk, cost, or network analysis.

### Simulate

Evaluate how a proposed intervention affects the modeled environment or scenario.

### Compare

Compare alternative scenarios using common metrics.

### Recommend

Use validated analysis and AI-assisted interpretation to generate a structured planning recommendation.

---

# 23. Architectural Principles

## Separation of Concerns

Frontend, backend, ETL, database, analytical engines, and AI orchestration should remain independently understandable.

## Backend as Planning Authority

Authoritative planning calculations and persisted scenario state belong to the backend.

## Deterministic First

Spatial, numerical, and optimization results should come from deterministic tools wherever practical.

## AI for Interpretation

LLMs are used for intent extraction, interpretation, validation support, and report synthesis rather than acting as an unverified numerical engine.

## Geospatial Correctness

CRS handling, geometry validation, spatial persistence, and metric calculations must be explicit.

## UI Responsiveness

The Cesium workspace should remain responsive while asynchronous backend jobs and analyses execute.

## Extensibility

New analysis modules, agents, datasets, and planning tools should be addable without redesigning the complete system.

---

# 24. Architectural Decision Summary

| Decision | Rationale |
| --- | --- |
| Next.js + React | Component-based application and structured routing |
| CesiumJS | 3D geospatial visualization and digital-twin interaction |
| Zustand | Lightweight domain-oriented frontend state management |
| FastAPI | Typed Python API layer suitable for GIS workloads |
| PostgreSQL + PostGIS | Authoritative spatial persistence and querying |
| GeoJSON | Interoperable exchange format for frontend spatial visualization |
| GeoPandas / Shapely / PyProj | Python geospatial processing pipeline |
| Specialized AI agents | Domain-specific interpretation and orchestration |
| Deterministic analysis tools | Reliable numerical and spatial outputs |
| Floating windows | Dense planning workspace without sacrificing map visibility |
| Versioned API | Stable contract for frontend/backend evolution |

---

# 25. Extension Points

### Frontend

- New planning windows
- New Cesium layers
- New visualization modes
- New workspace presets
- Additional scenario controls

### Backend

- New API routers
- New analytical services
- New optimization engines
- New job types
- Additional domain services

### AI

- New specialist agents
- Additional deterministic tools
- Alternative LLM providers
- Improved validation agents
- More advanced report synthesis

### Data

- Additional GIS datasets
- Government open-data sources
- Satellite/remote-sensing layers
- Real-time mobility data
- Infrastructure datasets

---

# 26. Summary

NAGAR-X follows a layered architecture in which the **Next.js/Cesium frontend provides the interactive digital-twin workspace**, while the **FastAPI backend provides authoritative application, planning, analysis, and orchestration services**.

**PostGIS** provides the persistent geospatial foundation, the **ETL layer** brings external geographic data into the system, deterministic **GIS/optimization engines** calculate measurable planning outputs, and the **AI orchestration layer** interprets those outputs and produces structured planning recommendations.

```text
                 NAGAR-X
                    │
       ┌────────────┴────────────┐
       │                         │
   EXPERIENCE                 INTELLIGENCE
       │                         │
       ▼                         ▼
 Next.js + Cesium          FastAPI + AI
       │                         │
       └────────────┬────────────┘
                    │
                    ▼
             GIS / Analysis
                    │
                    ▼
              PostgreSQL
                + PostGIS
                    ▲
                    │
                  ETL
                    ▲
                    │
             External GIS Data
```

This separation provides a foundation for evolving NAGAR-X from a visualization prototype into a scalable urban planning decision-support platform.
