"use client";
/**
 * Guided Development Planner. Product report §1 and §3.
 *
 * Implements the report's simple user flow without exposing the machinery:
 *
 *   1 set target  ->  2 choose priorities  ->  3 set constraints
 *   4 generate package  ->  5/6 build and compare Scenario A/B/C
 *
 * "The planner should make decisions, not calculations." So this panel only
 * ever asks for a target, some priorities and a budget; the spatial analysis,
 * siting, costing and ranking all happen server-side.
 *
 * Packages are shown as a dependency tree, never as a flat list: the report
 * is explicit that a hospital without access roads is an incomplete solution.
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import { SectionTitle, Empty } from "@/components/ui/Bits";
import { useWorkflowStore } from "@/stores/workflow-store";
import WorkflowErrorState from "@/components/workflow/WorkflowErrorState";

const PRIORITIES = [
  { key: "healthcare", label: "Healthcare" },
  { key: "education", label: "Education" },
  { key: "mobility", label: "Mobility" },
  { key: "facility_access", label: "Public access" },
  { key: "green_space", label: "Green space" },
  { key: "recreation", label: "Recreation" },
  { key: "resilience", label: "Resilience" },
  { key: "infrastructure", label: "Infrastructure" },
];

const KIND_ICON: Record<string, string> = {
  facility: "▣",
  road: "═",
  utility: "⚡",
  open_space: "❋",
};

const money = (n: number) => {
  if (!Number.isFinite(n)) return "—";
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${Math.round(n).toLocaleString()}`;
};

export default function DevelopmentPanel() {
  const [target, setTarget] = useState(10);
  const [picked, setPicked] = useState<string[]>([]);
  const [budget, setBudget] = useState<string>("");
  const [pkg, setPkg] = useState<any>(null);
  const [cmp, setCmp] = useState<any>(null);
  const [busy, setBusy] = useState<"" | "pkg" | "cmp">("");
  const [err, setErr] = useState<string | null>(null);

  const budgetNum = budget.trim() ? Number(budget) * 1e7 : null; // crore

  function toggle(k: string) {
    setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));
  }

  async function generate() {
    setBusy("pkg"); setErr(null); setCmp(null);
    try {
      const workflowStore = useWorkflowStore.getState();
      let sessId = workflowStore.context.backendSessionId;
      if (!sessId) {
        const startRes = await api.startWorkflow("improve");
        workflowStore.syncFromBackend(startRes);
        sessId = startRes.session_id;
      }

      const auditRes = await api.improveAudit(sessId);
      workflowStore.syncFromBackend(auditRes);

      const gapRes = await api.improveGaps({ session_id: sessId });
      workflowStore.syncFromBackend(gapRes);

      const pkgWfRes = await api.improvePackage({
        session_id: sessId,
        num_facilities: 3,
        facility_type: picked.includes("healthcare") ? "hospital" : "school",
        objective: "max_coverage"
      });
      workflowStore.syncFromBackend(pkgWfRes);

      const res = await api.developmentPackage({
        region: "adivali_devad",
        targetUplift: target,
        priorities: picked,
        budget: budgetNum,
      });
      setPkg(res);
    } catch (e: any) {
      setErr(e?.message ?? "Package generation failed.");
    } finally { setBusy(""); }
  }

  async function compare() {
    setBusy("cmp"); setErr(null);
    try {
      const workflowStore = useWorkflowStore.getState();
      let sessId = workflowStore.context.backendSessionId;
      if (sessId) {
        const simRes = await api.improveSimulate(sessId);
        workflowStore.syncFromBackend(simRes);

        const compWfRes = await api.improveCompare(sessId);
        workflowStore.syncFromBackend(compWfRes);
      }

      const res = await api.comparePackages({
        region: "adivali_devad",
        variants: [
          { name: "A · Balanced", targetUplift: target, priorities: [],
            budget: budgetNum },
          { name: "B · Your priorities", targetUplift: target,
            priorities: picked, budget: budgetNum },
          { name: "C · Resilience first", targetUplift: target,
            priorities: ["resilience", "mobility", "infrastructure"],
            budget: budgetNum },
        ],
      });
      setCmp(res);
    } catch (e: any) {
      setErr(e?.message ?? "Comparison failed.");
    } finally { setBusy(""); }
  }

  const primaries = (pkg?.actions ?? []).filter((a: any) => !a.parentId);
  const childrenOf = (id: string) =>
    (pkg?.actions ?? []).filter((a: any) => a.parentId === id);

  return (
    <div>
      {/* step 1 */}
      <SectionTitle>1 · Target improvement</SectionTitle>
      <div className="row" style={{ gap: 8, alignItems: "center" }}>
        <input type="range" min={2} max={40} step={1} value={target}
               onChange={(e) => setTarget(parseInt(e.target.value, 10))}
               style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 12, width: 44 }}>
          +{target}
        </span>
      </div>
      <div className="muted" style={{ fontSize: 10, marginBottom: 10 }}>
        points of development score to gain
      </div>

      {/* step 2 */}
      <SectionTitle>2 · Priorities</SectionTitle>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 4 }}>
        {PRIORITIES.map((p) => {
          const on = picked.includes(p.key);
          return (
            <button key={p.key} onClick={() => toggle(p.key)}
              style={{
                fontSize: 10, padding: "3px 8px", borderRadius: 11,
                cursor: "pointer", color: "inherit",
                border: on ? "1px solid rgba(56,189,248,0.8)"
                           : "1px solid rgba(148,163,184,0.3)",
                background: on ? "rgba(56,189,248,0.16)"
                               : "rgba(148,163,184,0.06)",
              }}>
              {p.label}
            </button>
          );
        })}
      </div>
      <div className="muted" style={{ fontSize: 10, marginBottom: 10 }}>
        {picked.length === 0
          ? "none selected — the gap analysis will choose"
          : `${picked.length} selected`}
      </div>

      {/* step 3 */}
      <SectionTitle>3 · Budget ceiling</SectionTitle>
      <div className="row" style={{ gap: 6, marginBottom: 10 }}>
        <input value={budget} onChange={(e) => setBudget(e.target.value)}
          placeholder="no limit" inputMode="decimal"
          style={{
            flex: 1, fontSize: 11, padding: "4px 7px", borderRadius: 5,
            background: "rgba(15,23,42,0.6)", color: "inherit",
            border: "1px solid rgba(148,163,184,0.3)",
          }} />
        <span className="muted" style={{ fontSize: 10 }}>₹ crore</span>
      </div>

      {/* step 4 / 5 */}
      <div className="row" style={{ gap: 6 }}>
        <button className="btn primary" style={{ flex: 1 }}
                disabled={!!busy} onClick={generate}>
          {busy === "pkg" ? "Generating…" : "Generate package"}
        </button>
        <button className="btn ghost" disabled={!!busy} onClick={compare}>
          {busy === "cmp" ? "…" : "Compare A/B/C"}
        </button>
      </div>

      {err && (
        <div style={{
          marginTop: 8, padding: "7px 9px", borderRadius: 6, fontSize: 11,
          background: "rgba(239,68,68,0.12)",
          border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5",
        }}>{err}</div>
      )}

      {/* package result */}
      {pkg && !cmp && (
        <>
          <SectionTitle>Recommended package</SectionTitle>
          <div className="row" style={{
            justifyContent: "space-between", padding: "8px 10px",
            borderRadius: 7, marginBottom: 8,
            background: "rgba(34,197,94,0.10)",
            border: "1px solid rgba(34,197,94,0.3)",
          }}>
            <div>
              <div className="muted" style={{ fontSize: 9.5 }}>score</div>
              <div className="mono" style={{ fontSize: 13 }}>
                {pkg.currentScore?.toFixed(0)} → {pkg.projectedScore?.toFixed(0)}
                <span style={{ color: "#22c55e", fontSize: 11 }}>
                  {" "}(+{pkg.expectedUplift?.toFixed(1)})
                </span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="muted" style={{ fontSize: 9.5 }}>total cost</div>
              <div className="mono" style={{ fontSize: 13 }}>
                {money(pkg.totalCost)}
              </div>
            </div>
          </div>

          {primaries.length === 0 && <Empty>No interventions recommended.</Empty>}

          {primaries.map((a: any) => (
            <div key={a.id} style={{
              marginBottom: 7, padding: "7px 9px", borderRadius: 6,
              background: "rgba(148,163,184,0.07)",
              border: "1px solid rgba(148,163,184,0.2)",
            }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span style={{ fontSize: 11.5, fontWeight: 600 }}>
                  {KIND_ICON[a.kind] ?? "•"} {a.label}
                </span>
                <span className="mono" style={{ fontSize: 10 }}>
                  {money(a.cost)}
                </span>
              </div>
              <div className="muted" style={{ fontSize: 10, marginTop: 3 }}>
                {a.rationale}
              </div>
              <div className="row" style={{ gap: 8, marginTop: 4 }}>
                <span className="mono" style={{ fontSize: 9.5, color: "#22c55e" }}>             
                  +{a.expectedUplift?.toFixed(2)} pts
                </span>
                {a.populationServed > 0 && (
                  <span className="mono muted" style={{ fontSize: 9.5 }}>
                    {Number(a.populationServed).toLocaleString()} served
                  </span>
                )}
                <span className="mono muted" style={{ fontSize: 9.5 }}>
                  {a.feasibility} feasibility
                </span>
              </div>
              {childrenOf(a.id).length > 0 && (
                <div style={{
                  marginTop: 6, paddingLeft: 9,
                  borderLeft: "2px solid rgba(56,189,248,0.4)",
                }}>
                  <div className="muted" style={{ fontSize: 9, marginBottom: 2 }}>
                    requires
                  </div>
                  {childrenOf(a.id).map((c: any) => (
                    <div key={c.id} className="row"
                         style={{ justifyContent: "space-between" }}>
                      <span style={{ fontSize: 10 }}>
                        {KIND_ICON[c.kind] ?? "•"} {c.label}
                      </span>
                      <span className="mono muted" style={{ fontSize: 9.5 }}>
                        {money(c.cost)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {(pkg.warnings ?? []).map((w: string, i: number) => (
            <div key={i} className="muted" style={{ fontSize: 9.5, marginTop: 4 }}>
              · {w}
            </div>
          ))}
        </>
      )}

      {/* comparison result */}
      {cmp && (
        <>
          <SectionTitle>Scenario comparison</SectionTitle>
          {(cmp.scenarios ?? []).map((s: any) => {
            const best = s.name === cmp.recommended;
            return (
              <div key={s.name} style={{
                marginBottom: 7, padding: "8px 10px", borderRadius: 7,
                background: best ? "rgba(34,197,94,0.10)"
                                 : "rgba(148,163,184,0.07)",
                border: best ? "1px solid rgba(34,197,94,0.45)"
                             : "1px solid rgba(148,163,184,0.2)",
              }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span style={{ fontSize: 11.5, fontWeight: 600 }}>
                    {s.name}{best && " ★"}
                  </span>
                  <span className="mono" style={{ fontSize: 10 }}>
                    {money(s.totalCost)}
                  </span>
                </div>
                <div className="row" style={{ gap: 10, marginTop: 4 }}>
                  <span className="mono" style={{ fontSize: 9.5, color: "#22c55e" }}>
                    +{(s.expectedUplift ?? 0).toFixed(1)} pts
                  </span>
                  <span className="mono muted" style={{ fontSize: 9.5 }}>
                    {s.actionCount} actions
                  </span>
                  <span className="mono muted" style={{ fontSize: 9.5 }}>
                    {s.costPerPoint ? `${money(s.costPerPoint)}/pt` : "no uplift"}
                  </span>
                </div>
              </div>
            );
          })}
          <div className="muted" style={{ fontSize: 9.5, marginTop: 6 }}>
            {cmp.recommendationBasis}
          </div>
          <button className="btn ghost" style={{ width: "100%", marginTop: 8 }}
                  onClick={() => setCmp(null)}>
            Back to package
          </button>
        </>
      )}
    </div>
  );
}
