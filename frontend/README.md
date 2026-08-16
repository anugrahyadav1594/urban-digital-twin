# NAGAR-X — Urban Digital Twin · Floating-Window Planning Workspace (frontend)

A desktop-style geospatial planning workspace featuring a full-viewport **CesiumJS 3D city & digital twin canvas**, a horizontal command navbar, compact status bars, and draggable / resizable / auto-aligning **floating tool windows**.

---

## 🚀 Getting Started

```bash
npm install     # Installs dependencies & copies CesiumJS build into public/cesium
npm run dev     # Starts Next.js dev server at http://localhost:3000 (auto-redirects to /workspace)
```

Node 20+ supported; Node 22+ recommended (CesiumJS engine requirement).

### Environment Configuration (`.env.local`)

Copy `.env.local.example` to `.env.local` to customize settings:

| Variable | Description | Default / Fallback |
| --- | --- | --- |
| `NEXT_PUBLIC_CESIUM_ION_TOKEN` | Cesium Ion Access Token for world terrain & imagery | Empty → Uses CartoDB / Esri dark basemaps |
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI backend URL | Empty → Silently switches to offline deterministic engine (`DEMO DATA` badge) |
| `NEXT_PUBLIC_CITY_LON` | Pilot city center longitude | `73.7389` (Pune, MH) |
| `NEXT_PUBLIC_CITY_LAT` | Pilot city center latitude | `18.5913` (Pune, MH) |

---

## ✨ Features & Recent Modifications

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
types/          TypeScript domain models and contracts
```

---

## 🔌 API & Backend Integration

The frontend client in `lib/api/client.ts` attempts to connect to `NEXT_PUBLIC_API_BASE_URL`. If the backend is unavailable or not configured, it gracefully falls back to the deterministic mock engine in `lib/mock.ts` (`DEMO DATA` status indicator).
