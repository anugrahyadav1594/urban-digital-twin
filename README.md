# NAGAR-X — Urban Digital Twin Workspace

An enterprise-grade **Urban Digital Twin & Geospatial Planning Platform** featuring a full-viewport **CesiumJS 3D city canvas**, interactive multi-window layout engine, real-world geospatial data layers, scenario simulation, and AI-assisted urban planning tools.

---

## 🛠️ Quick Start & Frontend Setup

### Prerequisites

- **Node.js**: `v20.0.0` or higher (`v22.x` recommended)
- **Package Manager**: `npm` (v10+), `yarn`, or `pnpm`
- **Browser**: Modern browser with WebGL 2.0 enabled

---

### Step-by-Step Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/anugrahyadav1594/urban-digital-twin.git
cd urban-digital-twin

# 2. Navigate to the frontend directory
cd frontend

# 3. Install dependencies & prepare Cesium assets
npm install

# 4. (Optional) Create local environment configuration
cp .env.local.example .env.local

# 5. Start the development server
npm run dev
```

Open **`http://localhost:3000`** in your web browser. The app will load the digital twin workspace at `/workspace`.

---

## ⚡ Available Commands

Run commands from the `frontend` directory:

| Command | Action |
| --- | --- |
| `npm run dev` | Starts Next.js development server at `http://localhost:3000` |
| `npm run build` | Compiles optimized Next.js production build |
| `npm run start` | Launches production server at `0.0.0.0:3000` |
| `npm run lint` | Runs Next.js ESLint checks |
| `node scripts/copy-cesium.mjs` | Copies static CesiumJS build files into `public/cesium/` |

---

## 🌟 Features Overview

- **3D Geospatial Globe Canvas**: Built with CesiumJS, featuring pilot city 3D building massings, parcel boundaries, waterbodies, and highway networks.
- **Auto-Align Window Engine**: Floating tool windows automatically tile, snap, and resize into optimal grid layouts without overlapping.
- **National Highways & Hydrography**: Layers for National Highway routes (`NH 48`, `NH 65`, etc.), real-world river corridors, and reservoirs.
- **Camera Controls & Altitude Floor**: Shortest-path home flight, True North heading re-alignment, and surface collision detection floor (`50m`).
- **Interactive Planning Tools**: Site suitability analysis, scenario creation, parcel inspector, job monitor, and AI planning assistant.

---

## 📁 Repository Structure

```
urban-digital-twin/
├── frontend/                 # Next.js 15 App Router Frontend
│   ├── app/                  # Application pages & globals
│   ├── cesium/               # CesiumViewer 3D scene & bridge
│   ├── components/           # UI components, floating windows, panels
│   ├── public/data/          # GeoJSON datasets (states, highways, water)
│   ├── scripts/              # Build scripts (copy-cesium.mjs)
│   └── stores/               # Zustand state stores
├── backend/                  # FastAPI Backend API (optional)
├── data/                     # GIS Data Processing Pipeline
└── README.md
```

For detailed frontend documentation, view [frontend/README.md](file:///home/shikhar/Desktop/urban-digital-twin/frontend/README.md).
