"use client";
import { useEffect } from "react";
import { useMapStore } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { SectionTitle } from "@/components/ui/Bits";
import { CITY } from "@/lib/city-model";
import { num } from "@/lib/format";

export default function SimulationPanel() {
  const { year, setYear, playing, setPlaying } = useMapStore();
  const scenario = useScenarioStore((s) => s.scenarios.find((x) => x.id === s.activeId)!);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const y = useMapStore.getState().year;
      if (y >= 2040) { useMapStore.getState().setPlaying(false); return; }
      useMapStore.getState().setYear(y + 1);
    }, 550);
    return () => clearInterval(t);
  }, [playing]);

  const t = (year - 2026) / 14;
  const pop = Math.round(CITY.population * (1 + (scenario.populationGrowthPct / 100) * t));
  const demandBeds = Math.round((pop / 1000) * 2.1);
  const builtUp = Math.round(38 + t * scenario.populationGrowthPct * 0.55);

  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="btn primary" style={{ width: 46 }} onClick={() => setPlaying(!playing)}>{playing ? "❚❚" : "▶"}</button>
          <button className="btn ghost" onClick={() => { setPlaying(false); setYear(2026); }}>Reset</button>
        </div>
        <div className="mono" style={{ fontSize: 22 }}>{year}</div>
      </div>

      <input type="range" min={2026} max={2040} value={year} style={{ width: "100%" }} onChange={(e) => setYear(Number(e.target.value))} />
      <div className="row mono muted" style={{ fontSize: 10, marginTop: 2 }}><span>2026</span><span>2033</span><span>2040</span></div>

      <SectionTitle>Projected state · {scenario.name}</SectionTitle>
      <div className="metrics">
        <div className="metric"><div className="l">Population</div><div className="v">{num(pop)}</div></div>
        <div className="metric"><div className="l">Hospital beds needed</div><div className="v">{num(demandBeds)}</div></div>
        <div className="metric"><div className="l">Built-up area</div><div className="v">{builtUp}%</div></div>
        <div className="metric"><div className="l">Water demand</div><div className="v">{(pop * 0.135 / 1000).toFixed(1)}<span style={{ fontSize: 11 }}> MLD</span></div></div>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
        Building volumes in the 3D city scale with the projected growth curve of the active scenario.
      </div>
    </div>
  );
}
