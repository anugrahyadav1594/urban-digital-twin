# NAGAR-X — Urban Digital Twin

An AI-assisted urban planning and geospatial decision-support platform that combines a **CesiumJS 3D digital-twin workspace**, **FastAPI planning API**, **PostGIS geospatial storage**, real **OpenStreetMap ingestion**, and a **multi-agent AI planning workflow** for evaluating urban infrastructure scenarios.

> **Project Status:** Active Development

---

## Overview

NAGAR-X transforms urban-planning requirements into structured, data-backed planning workflows.

The platform combines:

- **3D city visualization** using CesiumJS
- **Interactive planning tools** through a floating-window workspace
- **Geospatial analysis** powered by PostgreSQL/PostGIS
- **OpenStreetMap data ingestion**
- **AI-assisted planning and decision support**
- **Deterministic spatial and quantitative analysis**
- **Scenario, risk, cost, and site-suitability evaluation**
- **Automated planning report generation**

The project is structured as a full-stack urban digital-twin platform with dedicated frontend, backend, database, ETL, AI, and infrastructure layers.

---

## Core Capabilities

### 3D Urban Digital Twin

The frontend provides a full-viewport CesiumJS 3D environment for visualizing and interacting with the urban model.

Features include:

- 3D geographic visualization
- City and infrastructure layers
- Camera navigation
- True-north alignment
- Spatial selection
- Collision detection
- Map controls
- Geographic overlays
- Dynamic layer visibility

### Floating Planning Workspace

NAGAR-X uses a desktop-style interface rather than a traditional fixed sidebar.

The workspace includes:

- Horizontal command navbar
- Floating tool windows
- Draggable panels
- Resizable panels
- Window snapping
- Window maximizing/restoring
- Automatic window alignment
- Workspace presets
- Taskbar
- Command palette

Major workspace areas include:

- City
- Layers
- Planning
- Analysis
- Scenario
- Simulation
- Compare
- AI
- Workspace

### Geospatial Data Pipeline

The ETL layer processes real OpenStreetMap data using:

- GeoPandas
- Shapely
- PyProj
- OSMnx
- Pandas
- SQLAlchemy

Supported urban layers include:

- Roads
- Buildings
- Facilities
- Water bodies
- Land parcels
- Population zones

The ingestion pipeline is designed to report failed data retrieval instead of silently replacing real-world data with fabricated records.

### AI Planning Orchestration

The backend contains a multi-agent planning workflow coordinated through an `Orchestrator`.

The workflow includes:

1. Planning intent extraction
2. Spatial analysis
3. GIS interpretation
4. Cost analysis
5. Risk assessment
6. Critic validation
7. Report generation

The system combines AI interpretation with deterministic analytical tools for reliable quantitative outputs.

---

## Architecture

```text
                         ┌──────────────────────────┐
                         │        User / Planner     │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                 ┌────────────────────────────────────────┐
                 │      Next.js + React + CesiumJS        │
                 │                                        │
                 │  3D Twin • Navbar • Floating Windows   │
                 │  Layers • Planning • Analysis • AI     │
                 └────────────────────┬───────────────────┘
                                      │ HTTP / REST
                                      ▼
                 ┌────────────────────────────────────────┐
                 │             FastAPI Backend             │
                 │                                        │
                 │ API v1 • Storage • Planning Workflow   │
                 │ AI Agents • Deterministic Tooling       │
                 └───────────────┬────────────────────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             │                   │                    │
             ▼                   ▼                    ▼
      ┌─────────────┐     ┌──────────────┐     ┌───────────────┐
      │   PostGIS   │     │ AI / Agents  │     │ OSM / ETL     │
      │ City Model  │     │ Orchestrator │     │ Geo Ingestion │
      └─────────────┘     └──────────────┘     └───────────────┘
```

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript |
| 3D / GIS | CesiumJS |
| State Management | Zustand |
| Backend | FastAPI, Uvicorn |
| Validation / Config | Pydantic |
| ORM / Database | SQLAlchemy, GeoAlchemy2 |
| Database | PostgreSQL + PostGIS |
| Geospatial Processing | GeoPandas, Shapely, PyProj, OSMnx |
| Analysis | NetworkX, NumPy, SciPy, Pandas, OR-Tools |
| HTTP | Requests, HTTPX |
| Migrations | Alembic |
| Local Infrastructure | Docker Compose |
| Developer Automation | Make |

---

## Repository Structure

```text
urban-digital-twin/
│
├── backend/
│   ├── app/
│   │   ├── agents/          # AI agents and orchestration
│   │   ├── api/             # Versioned API routes
│   │   ├── core/            # Configuration
│   │   └── storage/         # Database/storage layer
│   │
│   ├── tests/               # Backend tests
│   ├── Dockerfile
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── app/                 # Next.js App Router
│   ├── cesium/              # Cesium viewer and map bridge
│   ├── components/          # UI, panels and layout
│   ├── stores/              # Zustand stores
│   ├── lib/                 # API and application utilities
│   ├── public/              # Static files and datasets
│   ├── scripts/             # Build utilities
│   └── types/               # TypeScript contracts
│
├── etl/                     # Geospatial data ingestion
├── db/                      # Database schema and seed scripts
├── data/                    # Project datasets
├── cache/                   # Local cache
├── infra/                   # Infrastructure configuration
├── docs/                    # Documentation
│
├── ARCHITECTURE.md
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Requirements

Before running the project, install:

- Git
- Docker
- Docker Compose
- Python 3
- Node.js 20+
- npm 10+
- Modern browser with WebGL 2.0 support

Optional:

- Cesium Ion access token
- Internet access for OpenStreetMap/Overpass ingestion

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/anugrahyadav1594/urban-digital-twin.git
cd urban-digital-twin
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Review the database and CRS configuration before starting the application.

> Never commit real passwords, API keys, tokens, or other secrets.

---

## Database Setup

Start the local PostGIS instance:

```bash
make db-up
```

The Docker configuration uses:

```text
PostgreSQL + PostGIS
postgis/postgis:17-3.5
```

Useful commands:

```bash
make db-up
make db-down
make db-reset
make db-logs
make doctor
make check
```

---

## Backend Setup

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

API:

```text
http://localhost:8000/api/v1
```

---

## Frontend Setup

Open a new terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start development server:

```bash
npm run dev
```

Frontend:

```text
http://localhost:3000
```

Cesium static assets are automatically copied through the frontend `postinstall` process.

If required, manually run:

```bash
node scripts/copy-cesium.mjs
```

---

## Environment Variables

### Backend

The root `.env.example` contains configuration for:

```env
POSTGIS_HOST=localhost
POSTGIS_PORT=5432
POSTGIS_DB=nagar_x_db
POSTGIS_USER=postgres
POSTGIS_PASSWORD=postgres

STORAGE_SRID=4326
ANALYSIS_SRID=32643

ACTIVE_DATASET_VERSION=1

DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_ECHO=false
SQL_STATEMENT_TIMEOUT_MS=30000
```

### Frontend

Create the frontend environment file:

```bash
cp .env.local.example .env.local
```

Example:

```env
NEXT_PUBLIC_CESIUM_ION_TOKEN=

NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

NEXT_PUBLIC_CITY_LON=73.7389
NEXT_PUBLIC_CITY_LAT=18.5913
```

---

## Frontend Commands

| Command | Description |
| --- | --- |
| `npm run dev` | Start development server |
| `npm run build` | Build production application |
| `npm run start` | Start production application |
| `npm run lint` | Run linting |
| `node scripts/copy-cesium.mjs` | Copy Cesium assets |

Production:

```bash
npm run build
npm run start
```

---

## OpenStreetMap ETL

The project contains a real OpenStreetMap ingestion pipeline.

Run the default pilot ingestion:

```bash
python -m etl.ingest_osm
```

Increase the ingestion area:

```bash
python -m etl.ingest_osm --scale 3
```

Perform a dry run:

```bash
python -m etl.ingest_osm --dry-run
```

The ETL system processes real-world geospatial information and generates a layer-level ingestion report.

Example layers:

```text
Roads
Buildings
Facilities
Water Bodies
Land Parcels
Population Zones
```

---

## AI Planning Workflow

The main orchestration layer is located at:

```text
backend/app/agents/orchestrator.py
```

The workflow is:

```text
User Planning Request
          │
          ▼
   Planning Agent
          │
          ▼
   Intent Extraction
          │
          ▼
Deterministic Analysis
          │
    ┌─────┼────────┬─────────┐
    ▼     ▼        ▼         ▼
Population GIS    Risk      Cost
    │     │        │         │
    └─────┴────────┴─────────┘
                  │
                  ▼
       Specialized Agents
                  │
                  ▼
          Critic Validation
                  │
                  ▼
          Report Generation
                  │
                  ▼
          Planning Result
```

### AI Agents

The orchestration layer contains:

- `PlanningAgent`
- `GISAgent`
- `CostAgent`
- `RiskAgent`
- `CriticAgent`
- `ReportAgent`
- `LLMClient`

### Deterministic Analysis

The workflow can perform:

- Population analysis
- Density analysis
- Travel-time calculation
- Distance calculation
- Constraint checking
- Cost estimation
- Site suitability scoring

The architecture separates deterministic calculations from AI-based interpretation.

---

## Coordinate Reference System

The project follows a defined CRS policy.

| Purpose | CRS |
| --- | --- |
| Storage | `EPSG:4326` |
| Analysis | `EPSG:32643` |

`EPSG:4326` is used for geographic storage.

`EPSG:32643` is used for projected metric analysis for the Navi Mumbai pilot region.

---

## Database Workflow

The recommended database workflow is:

```text
make db-up
     │
     ▼
Database Health Check
     │
     ▼
Schema Validation
     │
     ▼
Demo Data Seed
     │
     ▼
Integration Tests
```

Run the entire verification process:

```bash
make verify
```

Individual commands:

```bash
make check
make seed
make test
```

---

## Development Workflow

```text
Clone Repository
       │
       ▼
Configure Environment
       │
       ▼
Start PostGIS
       │
       ▼
Start FastAPI
       │
       ▼
Start Next.js
       │
       ▼
Run Verification
       │
       ▼
Develop / Test
```

Recommended initial command:

```bash
make verify
```

---

## Frontend Workspace

The frontend follows a desktop-style planning environment.

### Navigation

The horizontal navbar organizes the main application capabilities.

### Floating Windows

Planning tools are displayed as floating windows that can be:

- Moved
- Resized
- Maximized
- Restored
- Snapped
- Automatically aligned

### Command Palette

```text
Ctrl + K
```

or:

```text
Cmd + K
```

opens the command palette.

### Window Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl/Cmd + K` | Command palette |
| `Ctrl/Cmd + 1..6` | Toggle workspace windows |
| `Esc` | Close focused window |
| Double-click title bar | Maximize / restore |
| Drag to screen edge | Snap window |

---

## Backend API

The FastAPI application is defined in:

```text
backend/app/main.py
```

The backend provides:

- REST API
- OpenAPI documentation
- Database connectivity checks
- PostGIS diagnostics
- CORS configuration
- Structured database failure responses
- Application-level exception handling
- Versioned routing

API prefix:

```text
/api/v1
```

Interactive documentation:

```text
http://localhost:8000/docs
```

---

## Database Architecture

```text
                FastAPI
                   │
                   ▼
              SQLAlchemy
                   │
                   ▼
             GeoAlchemy2
                   │
                   ▼
          PostgreSQL + PostGIS
                   │
                   ▼
            Urban Data Model
```

PostGIS provides spatial storage and querying for the digital-twin dataset.

The local database is containerized using Docker Compose and persists its data using a Docker volume.

---

## Project Documentation

Additional documentation:

```text
ARCHITECTURE.md
frontend/README.md
docs/
Makefile
.env.example
```

Important files:

| File | Purpose |
| --- | --- |
| `ARCHITECTURE.md` | System architecture |
| `frontend/README.md` | Frontend documentation |
| `docker-compose.yml` | PostGIS configuration |
| `Makefile` | Development commands |
| `.env.example` | Backend environment template |
| `backend/app/main.py` | FastAPI entry point |
| `backend/app/agents/orchestrator.py` | AI orchestration |
| `etl/ingest_osm.py` | OSM ingestion |
| `db/schema.sql` | Database schema |

---

## Verification

Run:

```bash
make verify
```

The command performs:

```text
Database Startup
      ↓
Database Connectivity Check
      ↓
Schema Check
      ↓
Demo Data Seeding
      ↓
Integration Tests
```

For troubleshooting:

```bash
make doctor
```

---

## Current Development Status

NAGAR-X is an actively developed engineering prototype.

Current project areas include:

- 3D CesiumJS digital-twin visualization
- Next.js planning workspace
- Floating-window interface
- FastAPI backend
- PostGIS integration
- OpenStreetMap ingestion
- Geospatial processing
- AI planning orchestration
- Deterministic analytical tools
- Database verification
- Backend integration testing

Some components are still evolving and require further validation, testing, security hardening, and deployment work before production use.

---

## Contributing

Contributions should maintain the separation between:

- Frontend UI and state
- Cesium visualization
- Backend API
- Deterministic analysis
- Geospatial ETL
- Database/storage
- AI orchestration

When changing configuration or development workflows, update the relevant documentation and environment examples.

---

## Security

Never commit:

```text
.env
.env.local
API keys
Cesium tokens
Database passwords
LLM credentials
```

Use environment files for local configuration and secrets.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Repository

GitHub:

https://github.com/anugrahyadav1594/urban-digital-twin

Default branch:

```text
main
```

---

## NAGAR-X

**AI-assisted urban planning.**

**Geospatial intelligence.**

**3D digital twins.**

**Data-driven infrastructure decisions.**