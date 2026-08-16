# NAGAR-X — Urban Digital Twin · Floating-Window Planning Workspace (frontend)

A desktop-style geospatial planning workspace: a full-viewport **CesiumJS 3D city** as the
application canvas, a horizontal command navbar, and every tool as a **draggable / resizable
floating window**.

## Run

```bash
npm install     # also copies the CesiumJS build into public/cesium
npm run dev     # http://localhost:3000  ->  redirects to /workspace
```

Node 20+ works, Node 22+ recommended (CesiumJS declares `engines.node >= 22`).

Optional `.env.local` (copy from `.env.local.example`):

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_CESIUM_ION_TOKEN` | Cesium Ion token → world terrain / imagery. Empty = CARTO dark basemap, no token needed. |
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI backend. Unreachable → the app silently uses the deterministic demo engine (`DEMO DATA` badge). |
| `NEXT_PUBLIC_CITY_LON` / `_LAT` | Pilot city centre. |

## What is implemented

**M1 Workspace foundation** — Next.js 15 (App Router) + TypeScript + Zustand + Cesium,
top navbar, WindowManager, FloatingWindow (drag, 8-way resize, minimize, maximize, close,
focus/z-index, edge snapping, pin left/right, per-window menu), taskbar, command palette,
`localStorage` layout persistence, workspace presets, keyboard shortcuts.

**M2/M3 Digital twin** — procedural pilot city (676 parcels, 3D buildings, road network,
river corridor, facilities), layer system with visibility + opacity, feature picking →
Inspector, legend.

**M4 Planning** — planning toolbar (select / draw road / place hospital, school, fire station /
draw zone / measure), site suitability with criteria weights, road alignment drawing with
impact readout and "add to scenario".

**M5 Scenarios** — scenario manager, growth slider, lifecycle status, change set.

**M6 Analysis** — accessibility, flood risk, suitability; async job pipeline with staged
progress; generic result model (metrics, table, ranked entities, map binding, provenance).

**M7 Decision support** — scenario comparison matrix with winner + trade-off explanation,
AI planning assistant with a live agent trace over deterministic tools.

**M8 Polish** — presets, persistence, shortcuts, snapping, demo/offline mode, graceful
Cesium failure fallback.

## Keyboard

| Shortcut | Action |
| --- | --- |
| `⌘/Ctrl + K` | Command palette (windows, presets, camera, parcel ids) |
| `⌘/Ctrl + 1..6` | Layers / Planning / Analysis / Scenario / AI / Compare |
| `Esc` | Close focused window |
| Double-click title bar | Maximize / restore |
| Drag to screen edge | Snap left / right half, top = maximize |

## Structure

```
app/            layout, /workspace page
cesium/         CesiumViewer + map-bridge (imperative React ⇄ Cesium API)
components/
  layout/       Workspace, TopNavbar, WindowManager, Taskbar, CommandPalette
  windows/      FloatingWindow + window registry
  panels/       one panel per tool window
  ui/           metric cards, bars, job progress
stores/         window, layer, selection, scenario, analysis, job, ai, map (Zustand)
lib/            api client, city model, mock engine, constants
types/          domain contracts shared with the backend
```

## Swapping in the real backend

`lib/api/client.ts` tries `NEXT_PUBLIC_API_BASE_URL` first and falls back to
`lib/mock.ts`. Implement `/city`, `/features/{id}`, `/scenarios`, `/planning/suitability`,
`/analysis/accessibility`, `/analysis/risk` returning the shapes in `types/index.ts`
and the UI switches over with no component changes.
