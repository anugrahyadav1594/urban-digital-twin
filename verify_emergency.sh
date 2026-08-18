#!/usr/bin/env bash
# Verify the emergency route finder and disaster simulator against the REAL DB.
# Backend must be running.  Usage: bash verify_emergency.sh
set -uo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"
J='Content-Type: application/json'
# Incident location. Override:  LON=73.14 LAT=19.00 bash verify_emergency.sh
LON="${LON:-73.135}"
LAT="${LAT:-19.002}"

echo "=== 0. backend reachable ==="
code=$(curl -s -o /tmp/e_ready.json -w '%{http_code}' "$API/ready")
echo "GET /ready -> HTTP $code"
if [ "$code" != "200" ]; then
  echo "FAIL: backend not ready. Start it, then re-run."
  cat /tmp/e_ready.json 2>/dev/null; exit 1
fi

echo
echo "=== 1. catalogue (drives the UI controls) ==="
curl -s "$API/emergency/catalogue" | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("  hazards :", ", ".join(h["id"] for h in d.get("hazards", [])))
for m in d.get("measures", []):
    ap = ",".join(m["appliesTo"]) or "all"
    print("    %-20s -%3d%% %-22s [%s]" % (m["id"], m["effect"], m["reduces"], ap))
'

echo
echo "=== 2. ROUTE FINDER — which unit responds, and how fast ==="
curl -s -X POST "$API/emergency/route" -H "$J" \
  -d "{\"lon\":$LON,\"lat\":$LAT,\"responderType\":\"fire_station\",\"topN\":3}" \
| python3 -c '
import sys, json
d = json.load(sys.stdin)
if "detail" in d:
    print("  ERROR:", d["detail"]); raise SystemExit
rs = d.get("records", [])
if not rs:
    print("  no reachable station"); 
for r in rs:
    flag = "OK " if r["within_target"] else "LATE"
    print("  #%d %s %-28s %6.2f min  %6.2f km  %d pts" % (
        r["rank"], flag, r["station_name"][:28], r["response_time_min"],
        r["distance_m"] / 1000.0, len(r["path"])))
for w in d.get("warnings", []): print("  !", w)
'

echo
echo "=== 3. blocked roads must change the answer ==="
echo "    (grab two real road ids and close them)"
IDS=$(curl -s "$API/layers/roads/geojson?limit=2" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    ids = [str(f["properties"].get("id")) for f in d.get("features", [])[:2]]
    print(",".join(i for i in ids if i and i != "None"))
except Exception:
    print("")
')
if [ -n "$IDS" ]; then
  echo "    blocking road ids: $IDS"
  BLK=$(python3 -c "print(__import__('json').dumps('$IDS'.split(',')))")
  curl -s -X POST "$API/emergency/route" -H "$J" \
    -d "{\"lon\":$LON,\"lat\":$LAT,\"topN\":1,\"blockedRoadIds\":$BLK}" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
n = d.get("network") or {}
print("    edges blocked in graph:", n.get("blocked", 0))
for r in d.get("records", []):
    print("    -> %-28s %.2f min" % (r["station_name"][:28], r["response_time_min"]))
if n.get("blocked", 0) == 0:
    print("    NOTE: 0 edges blocked - those road ids are not on the routed graph.")
'
else
  echo "    (skipped: could not read road ids from /layers/roads/geojson)"
fi

echo
echo "=== 4. DISASTER SIMULATOR — every hazard, with and without measures ==="
for HZ in fire flood earthquake chemical; do
  curl -s -X POST "$API/emergency/simulate" -H "$J" \
    -d "{\"hazardType\":\"$HZ\",\"lon\":$LON,\"lat\":$LAT,\"measures\":[\"early_warning\",\"building_retrofit\",\"road_redundancy\",\"flood_barrier\",\"fire_break\",\"backup_power\"]}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'detail' in d:
    print('  $HZ -> ERROR', d['detail']); raise SystemExit
b = {m['name']: m['value'] for m in d['baseline']['metrics']}
a = {m['name']: m['value'] for m in d['mitigated']['metrics']}
print(f\"  {'$HZ':11} radius {b['hazard_radius_m']:>7.0f} -> {a['hazard_radius_m']:<7.0f}  \"
      f\"people {b['population_at_risk']:>9,.0f} -> {a['population_at_risk']:<9,.0f}  \"
      f\"roads {b['roads_blocked']:>4.0f} -> {a['roads_blocked']:<4.0f}\")
r = d.get('response') or {}
def f(x):
    if not x: return 'CUT OFF'
    s = f\"{x['response_time_min']:.2f}m\"
    if x.get('staging_distance_m'): s += f\" (staged {x['staging_distance_m']:.0f}m out)\"
    return s
if 'error' not in r:
    print(f\"              response  normal {f(r.get('normal'))}  |  during {f(r.get('during_event'))}  |  +measures {f(r.get('with_measures'))}\")
"
done

echo
echo "=== 5. a measure that does not apply must say so ==="
curl -s -X POST "$API/emergency/simulate" -H "$J" \
  -d "{\"hazardType\":\"fire\",\"lon\":$LON,\"lat\":$LAT,\"measures\":[\"flood_barrier\"]}" \
| python3 -c '
import sys, json
d = json.load(sys.stdin)
print("  warnings:", (d.get("mitigated") or {}).get("warnings"))
'

echo
echo "=== 6. bad input is rejected ==="
for BODY in '{"hazardType":"zombie","lon":73.1,"lat":19.0}' \
            '{"hazardType":"fire","lon":73.1,"lat":19.0,"measures":["magic"]}' \
            '{"hazardType":"fire","lon":999,"lat":19.0}'; do
  c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/emergency/simulate" -H "$J" -d "$BODY")
  echo "  HTTP $c  <- $BODY"
done

echo
echo "Expected: section 2 lists stations fastest-first; section 3 changes the"
echo "route or the count; section 4 shows people/roads DROPPING with measures;"
echo "section 5 warns about flood_barrier on a fire; section 6 all 422."
