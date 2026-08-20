"use client";
/**
 * City Scorecard. Product report §2 and §5.
 *
 * Shows the overall development score, every dimension's contribution and
 * the gap against the paired benchmark city, so a planner can see not just
 * what the score is but why.
 *
 * Weights are editable here because the report requires the scoring formula
 * to stay configurable until the framework is approved.
 */
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { SectionTitle, Empty } from "@/components/ui/Bits";

const REGIONS = [
  { id: "adivali_devad", label: "Adivali-devad (NAINA)" },
  { id: "jnpt_port", label: "JNPT Port" },
  { id: "chandigarh", label: "Chandigarh Sector 17" },
  { id: "rotterdam", label: "Rotterdam" },
];

function bandColor(score: number | null): string {
  if (score === null) return "#64748b";
  if (score >= 75) return "#22c55e";
  if (score >= 50) return "#eab308";
  if (score >= 25) return "#f97316";
  return "#ef4444";
}

/** Horizontal bar with the benchmark drawn as a marker line. */
function DimensionBar({ d }: { d: any }) {
  const score = d.score as number | null;
  const bench = d.benchmarkScore as number | null;
  const pct = score === null ? 0 : Math.max(0, Math.min(100, score));
  return (
    <div style={{ marginBottom: 9 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 11 }}>{d.label}</span>
        <span className="mono" style={{ fontSize: 10, color: bandColor(score) }}>
          {score === null ? "n/a" : score.toFixed(0)}
          {bench !== null && (
            <span className="muted"> / {bench.toFixed(0)}</span>
          )}
        </span>
      </div>
      <div style={{
        position: "relative", height: 7, borderRadius: 4,
        background: "rgba(148,163,184,0.18)", overflow: "visible",
      }}>
        <div style={{
          width: `${pct}%`, height: "100%", borderRadius: 4,
          background: bandColor(score),
          transition: "width .35s ease",
        }} />
        {bench !== null && (
          <div
            title={`Benchmark ${bench.toFixed(0)}`}
            style={{
              position: "absolute", left: `${Math.min(100, bench)}%`, top: -2,
              width: 2, height: 11, background: "#e2e8f0", opacity: 0.85,
            }}
          />
        )}
      </div>
      {!d.measurable && (
        <div className="muted" style={{ fontSize: 9.5, marginTop: 2 }}>
          not measurable — {d.note}
        </div>
      )}
      {d.measurable && d.raw !== null && (
        <div className="muted" style={{ fontSize: 9.5, marginTop: 2 }}>
          {d.raw} {d.unit}
          {d.benchmarkRaw != null && ` · benchmark ${d.benchmarkRaw} ${d.unit}`}
        </div>
      )}
    </div>
  );
}

export default function ScorecardPanel() {
  const [region, setRegion] = useState("adivali_devad");
  const [card, setCard] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showWeights, setShowWeights] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({});

  async function load(r = region, w: Record<string, number> | null = null) {
    setBusy(true); setErr(null);
    try {
      const res = w && Object.keys(w).length
        ? await api.cityScoreWeighted(r, w)
        : await api.cityScore(r);
      if (!res) { setErr("Backend unreachable."); setCard(null); }
      else setCard(res);
    } catch (e: any) {
      setErr(e?.message ?? "Scoring failed."); setCard(null);
    } finally { setBusy(false); }
  }

  useEffect(() => { load("adivali_devad"); /* eslint-disable-next-line */ }, []);

  const dims = card?.dimensions ?? [];
  const overall = card?.overallScore ?? null;
  const bench = card?.benchmarkScore ?? null;

  return (
    <div>
      <div className="row" style={{ gap: 6, marginBottom: 8 }}>
        <select
          value={region}
          onChange={(e) => { setRegion(e.target.value); load(e.target.value); }}
          style={{
            flex: 1, fontSize: 11, padding: "4px 6px", borderRadius: 5,
            background: "rgba(15,23,42,0.6)", color: "inherit",
            border: "1px solid rgba(148,163,184,0.3)",
          }}
        >
          {REGIONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
        <button className="btn ghost" style={{ padding: "4px 9px" }}
                disabled={busy} onClick={() => load()}>
          {busy ? "…" : "Rescore"}
        </button>
      </div>

      {err && (
        <div style={{
          padding: "7px 9px", borderRadius: 6, fontSize: 11, marginBottom: 8,
          background: "rgba(239,68,68,0.12)",
          border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5",
        }}>{err}</div>
      )}

      {!card && !err && <Empty>{busy ? "Scoring…" : "No scorecard yet."}</Empty>}

      {card && (
        <>
          {/* headline */}
          <div style={{
            display: "flex", alignItems: "baseline", gap: 10,
            padding: "10px 12px", borderRadius: 8, marginBottom: 10,
            background: "rgba(148,163,184,0.08)",
            border: "1px solid rgba(148,163,184,0.2)",
          }}>
            <div style={{
              fontSize: 30, fontWeight: 700, lineHeight: 1,
              color: bandColor(overall),
            }}>
              {overall === null ? "—" : overall.toFixed(0)}
            </div>
            <div style={{ flex: 1 }}>
              <div className="muted" style={{ fontSize: 10 }}>
                development score / 100
              </div>
              {bench !== null && (
                <div style={{ fontSize: 10.5, marginTop: 2 }}>
                  {card.benchmark?.label}:{" "}
                  <span className="mono">{bench.toFixed(0)}</span>{" "}
                  <span style={{
                    color: (card.benchmarkGap ?? 0) > 0 ? "#f97316" : "#22c55e",
                  }}>
                    ({(card.benchmarkGap ?? 0) > 0 ? "−" : "+"}
                    {Math.abs(card.benchmarkGap ?? 0).toFixed(1)})
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="muted" style={{ fontSize: 10, marginBottom: 8 }}>
            {card.dimensionsMeasured}/{card.dimensionsTotal} dimensions measured
            {card.population ? ` · ${Number(card.population).toLocaleString()} residents` : ""}
            {card.benchmarkSource === "published" && " · benchmark from published reference values"}
          </div>

          {/* Provenance of the inputs. Comparison cities are scored from OSM
              extracts with an estimated population, and that must be visible
              rather than buried in the warnings list. */}
          {card.populationSource === "estimated from building footprints" && (
            <div style={{
              padding: "6px 8px", borderRadius: 6, fontSize: 10,
              marginBottom: 8, lineHeight: 1.5,
              background: "rgba(234,179,8,0.10)",
              border: "1px solid rgba(234,179,8,0.35)",
            }}>
              <strong>Estimated inputs.</strong> Population is derived from{" "}
              {Number(card.populationEvidence?.buildingsResidential ?? 0).toLocaleString()}{" "}
              residential building footprints
              {card.populationEvidence?.assumedFloors
                ? ` (${card.populationEvidence.assumedFloors} floors, ${card.populationEvidence.m2PerPerson} m²/person)`
                : ""}, not a census count. Flood risk uses a
              distance-to-water proxy. Per-capita dimensions inherit this
              uncertainty.
              {card.analysisSrid ? ` Analysis CRS EPSG:${card.analysisSrid}.` : ""}
            </div>
          )}

          <SectionTitle>Dimensions</SectionTitle>
          {dims.map((d: any) => <DimensionBar key={d.key} d={d} />)}

          {/* configurable weights, per report §2 */}
          <button className="btn ghost" style={{ width: "100%", marginTop: 4 }}
                  onClick={() => setShowWeights((v) => !v)}>
            {showWeights ? "Hide weights" : "Adjust weights"}
          </button>
          {showWeights && (
            <div style={{ marginTop: 8 }}>
              {dims.map((d: any) => (
                <div key={d.key} className="row"
                     style={{ justifyContent: "space-between", padding: "2px 0" }}>
                  <span style={{ fontSize: 10 }}>{d.label}</span>
                  <input
                    type="number" step="0.1" min="0" max="5"
                    value={weights[d.key] ?? d.weight}
                    onChange={(e) => setWeights({
                      ...weights, [d.key]: parseFloat(e.target.value) || 0,
                    })}
                    style={{
                      width: 58, fontSize: 10, padding: "2px 5px",
                      borderRadius: 4, background: "rgba(15,23,42,0.6)",
                      color: "inherit",
                      border: "1px solid rgba(148,163,184,0.3)",
                    }}
                  />
                </div>
              ))}
              <div className="row" style={{ gap: 6, marginTop: 6 }}>
                <button className="btn primary" style={{ flex: 1 }}
                        disabled={busy}
                        onClick={() => load(region, weights)}>
                  Apply weights
                </button>
                <button className="btn ghost"
                        onClick={() => { setWeights({}); load(region); }}>
                  Reset
                </button>
              </div>
            </div>
          )}

          {(card.warnings ?? []).length > 0 && (
            <div className="muted" style={{ fontSize: 9.5, marginTop: 10 }}>
              {card.warnings.map((w: string, i: number) => (
                <div key={i} style={{ marginTop: 3 }}>· {w}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}