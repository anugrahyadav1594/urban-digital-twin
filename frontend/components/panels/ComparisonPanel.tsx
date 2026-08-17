"use client";
import { COMPARISON_ROWS } from "@/lib/mock";
import { SectionTitle } from "@/components/ui/Bits";
import { useScenarioStore } from "@/stores/scenario-store";

export default function ComparisonPanel() {
  const setActive = useScenarioStore((s) => s.setActive);
  const aWins = COMPARISON_ROWS.filter((r) => r.better === "a").length;
  const bWins = COMPARISON_ROWS.filter((r) => r.better === "b").length;
  const winner = aWins >= bWins ? "PLAN A" : "PLAN B";

  return (
    <div>
      <SectionTitle>Trade-off matrix · horizon 2040</SectionTitle>
      <table className="grid">
        <thead>
          <tr><th>Metric</th><th className="num">Base</th><th className="num">Plan A</th><th className="num">Plan B</th></tr>
        </thead>
        <tbody>
          {COMPARISON_ROWS.map((r) => (
            <tr key={r.metric}>
              <td>{r.metric}</td>
              <td className="num muted">{r.base}</td>
              <td className="num" style={{ color: r.better === "a" ? "var(--good)" : undefined }}>{r.a}</td>
              <td className="num" style={{ color: r.better === "b" ? "var(--good)" : undefined }}>{r.b}</td>
            </tr>
          ))}
          <tr className="win">
            <td><strong>Criteria won</strong></td>
            <td className="num">—</td>
            <td className="num"><strong>{aWins}</strong></td>
            <td className="num"><strong>{bWins}</strong></td>
          </tr>
        </tbody>
      </table>

      <div style={{ marginTop: 12, padding: 10, border: "1px solid rgba(52,211,153,.35)", borderRadius: 7, background: "rgba(52,211,153,.08)" }}>
        <div className="row">
          <strong style={{ letterSpacing: ".1em" }}>WINNER → {winner}</strong>
          <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={() => setActive("scn_plan_a")}>Make active</button>
        </div>
        <div className="muted" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.6 }}>
          Plan A serves 4 percentage points more population and cuts average emergency travel time by a further 2 minutes,
          at the cost of ₹6 Cr and 1,300 m² of additional land. Plan B is preferable only if the capital ceiling is
          hard-capped below ₹40 Cr; its medium flood exposure also carries a residual risk on the eastern infill belt.
        </div>
      </div>
    </div>
  );
}
