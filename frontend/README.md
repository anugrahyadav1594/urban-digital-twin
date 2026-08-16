# NAGAR-X — Urban Digital Twin · Floating-Window Planning Workspace (frontend)

A desktop-style geospatial planning workspace featuring a full-viewport **CesiumJS 3D city & digital twin canvas**, a horizontal command navbar, compact status bars, and draggable / resizable / auto-aligning **floating tool windows**.

---

## 💻 Frontend Setup Guide

### 1. Prerequisites

Ensure your development environment meets the following requirements:

- **Node.js**: `v20.0.0` or higher (`v22.x` recommended for optimal CesiumJS 1.144+ compatibility)
- **Package Manager**: `npm` (v10+), `yarn`, or `pnpm`
- **Modern Browser**: Chrome, Edge, Firefox, or Safari with WebGL 2.0 support enabled

Check your installed Node.js version:
```bash
node -v
npm -v
```

---

### 2. Installation & Quick Start

Navigate to the `frontend` directory and install all dependencies:

```bash
# 1. Change directory to frontend
cd frontend

# 2. Install dependencies (triggers postinstall script to copy Cesium static assets)
npm install

# 3. Start the development server
npm run dev
```

The application will start at **`http://localhost:3000`** (which automatically redirects to **`http://localhost:3000/workspace`**).

> **Note on CesiumJS Assets**: Running `npm install` automatically executes `node scripts/copy-cesium.mjs` via the `postinstall` hook. This copies required Cesium Workers, Widgets, Assets, and ThirdParty build files into `frontend/public/cesium`.

If Cesium assets are missing or fail to load, manually trigger the copy script:
```bash
node scripts/copy-cesium.mjs
```

---

### 3. Environment Variables Configuration

Copy the example environment file to create your local environment config:

```bash
cp .env.local.example .env.local
```

Configure `.env.local` according to your environment:

```env
# Optional: Cesium Ion Access Token for World Terrain & High-Res Imagery
# Leave empty to use default CartoDB / Esri dark basemaps without an API key
NEXT_PUBLIC_CESIUM_ION_TOKEN=

# Optional: FastAPI Backend URL
# If empty or backend is offline, the UI silently falls back to the local deterministic mock engine ("DEMO DATA" badge)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

# Target Pilot City Center Coordinates (Default: Pune, Maharashtra, India)
NEXT_PUBLIC_CITY_LON=73.7389
NEXT_PUBLIC_CITY_LAT=18.5913
```

---

### 4. Available NPM Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | **Primary command**: Starts Next.js development server bound to `0.0.0.0:3000` with hot-reloading |
| `npm run build` | Compiles optimized Next.js production build |
| `npm run start` | Runs production server bound to `0.0.0.0:3000` (*requires running `npm run build` first*) |
| `npm run lint` | Runs Next.js ESLint validation check |
| `node scripts/copy-cesium.mjs` | Copies static CesiumJS build files into `public/cesium/` |

> ⚠️ **Note on `npm run start` vs `npm run dev`**: To run the application during development, use **`npm run dev`**. Running `npm run start` directly without first compiling a production build (`npm run build`) will result in a *"Could not find a production build"* error.

---

### 5. Production Build & Deployment (Optional)

If you want to create and test a production build:

```bash
# 1. Compile production build
npm run build

# 2. Start production server
npm run start
```

---

## ✨ Features & Capabilities

### 📐 Compact Layout & Halved Bar Sizes
- **Compact Top Navbar**: Height set to **`66px`** (`NAVBAR_HEIGHT = 66`).
- **Compact Taskbar**: Height set to **`48px`** (`TASKBAR_HEIGHT = 48`).
- **Adjusted Floating Controls**: 3D globe controls panel bottom offset set to `64px` for optimal screen real estate.

### 🎨 SVG Vector Icons & Dropdown Animations
- **Vector Icons**: All navbar items, buttons, search controls, and group categories (`City`, `Scenario`, `Layers`, `Planning`, `Analysis`, `Simulation`, `Compare`, `AI`, `Workspace`) use clean vector SVG icons.
- **Animated Chevrons**: Dropdown chevron arrows (`ChevronDownIcon`) smoothly rotate **180°** (`transform: rotate(180deg)`) when open.
- **Slide-Down Animations**: Dropdown menus animate in with smooth scale and slide-down transitions (`keyframes menuSlideDown`).
- **Item Micro-Animations**: Dropdown menu items slide horizontally on hover (`transform: translateX(3px)`) with cyan highlights (`#38bdf8`).
- **Cyber Dark Select Theme**: `<select>` dropdowns and `<option>` lists styled with deep slate backgrounds (`#090e16`) and cyan active highlights.

### 🌐 National Highways, Waterbodies & Boundary Layers
- **National Highways Layer (`highways`)**:
  - **Esri World Transportation Reference Layer**: Toggleable layer displaying all National Highway routes (`NH 48`, `NH 65`, `NH 60`, `NH 52`, etc.) with official route numbers and road hierarchy across India.
  - **Curated Highway Data**: `india-highways.json` GeoJSON with midpoint screen-space NH route labels near Pune.
- **Waterbodies & Hydrography Layer (`water`)**:
  - **Esri World Ocean Reference Layer**: Toggleable layer displaying all natural waterbodies (oceans, seas, bays, gulfs, major rivers, lakes, and reservoirs) globally.
  - **Authentic Pune Waterbodies Data**: `pune-waterbodies.json` GeoJSON with real-world OpenStreetMap coordinates for Mula River, Mutha River, Pavana River, Indrayani River, Khadakwasla Dam, Pashan Lake, Katraj Lake, and Kasarsai Reservoir.
- **Boundaries & Places Layer**:
  - **Esri World Boundaries & Places Layer**: Authoritative international and state boundary lines.
  - **Inter-State GeoJSON Layer**: `india-states.json` inter-state boundary lines.

### 🧭 Camera Controls, Shortest-Path Navigation & Collision Detection
- **True North Re-Alignment (`alignNorth`)**: Re-aligns camera heading to 0° (True North) and re-orients pitch without drift.
- **Shortest-Path Flight (`flyHomeShortestRoute`)**: Calculates minimal arc rotation across the 3D globe when flying back home.
- **Surface Collision Detection & Floor**: Enabled `enableCollisionDetection = true` with `minimumZoomDistance = 50m` altitude floor to prevent the camera from clipping underground.
- **Missing Tile Prevention**: Configured `maximumLevel: 16` on Esri tile providers to eliminate *"Map data not available yet"* placeholder graphics during close zoom.

### 🪟 Intelligent Auto-Align Window Layout Engine
- **Flexible Tiling Algorithm (`computeAutoLayout`)**:
  - Automatically calculates optimal non-overlapping positions `(x, y)` and sizes `(width, height)` for any number $N$ of open windows.
  - Handles **1 window** (centered focus), **2 windows** (50/50 split), **3 windows** (1 main + 2 stacked columns), and **4+ windows** (dynamic $N$-matrix grid).
- **Auto-Alignment Triggers**:
  - Windows automatically position themselves when opened, closed, or when a workspace preset is applied.
  - Added **`Auto-align open windows`** button under **Workspace ▾ -> Layout** menu.
- **Smooth Layout Transitions**:
  - Added CSS transitions (`transition: left 0.32s, top 0.32s, width 0.32s, height 0.32s`) for seamless window repositioning.

---

## ⌨️ Keyboard Shortcuts & Controls

| Shortcut | Action |
| --- | --- |
| `⌘/Ctrl + K` | Command palette (search tools, windows, presets, camera points) |
| `⌘/Ctrl + 1..6` | Quick toggle windows (Layers / Planning / Analysis / Scenario / AI / Compare) |
| `Esc` | Close focused floating window |
| Double-click Title Bar | Maximize / restore window |
| Drag to Screen Edge | Snap window to left/right half or top maximize |

---

## 📁 Repository Structure

```
app/            Next.js App Router (/workspace, globals.css, layout.tsx)
cesium/         CesiumViewer.tsx (3D Globe), map-bridge.ts (imperative API bridge)
components/
  layout/       Workspace, TopNavbar, WindowManager, Taskbar, CommandPalette
  windows/      FloatingWindow.tsx, window registry, auto-alignment logic
  panels/       Tool panels (City, Layers, Planning, Scenario, Analysis, AI, etc.)
  ui/           Metric cards, status progress, UI primitives
stores/         Zustand state stores (window, layer, selection, scenario, analysis, job, ai, map)
lib/            API client, city model, mock engine, constants
public/data/    GeoJSON datasets (india-states.json, india-highways.json, pune-waterbodies.json)
scripts/        Build helper scripts (copy-cesium.mjs)
types/          TypeScript domain models and contracts
```
