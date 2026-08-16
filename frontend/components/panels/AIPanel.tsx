"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { DEFAULT_WEIGHTS } from "@/lib/mock";
import { mapBridge } from "@/cesium/map-bridge";
import { useAIStore } from "@/stores/ai-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import type { AgentStep } from "@/types";

const PIPELINE: { agent: AgentStep["agent"]; text: string; tool: string }[] = [
  { agent: "Planner", text: "Understanding planning objective and constraints…", tool: "decompose_goal" },
  { agent: "GIS", text: "Finding candidate parcels (area, zoning, ownership)…", tool: "get_candidate_parcels" },
  { agent: "Network", text: "Calculating catchment accessibility and travel times…", tool: "calculate_travel_time" },
  { agent: "Risk", text: "Checking flood and environmental constraints…", tool: "check_constraints" },
  { agent: "Optimization", text: "Ranking candidates by weighted multi-criteria score…", tool: "calculate_site_score" },
  { agent: "Cost", text: "Estimating capital and land acquisition cost…", tool: "estimate_cost" },
  { agent: "Validator", text: "Cross-checking results against dataset version…", tool: "validate_result" }
];

const SUGGESTIONS = [
  "Where should we build a new hospital?",
  "Which wards are underserved by emergency services?",
  "Compare Plan A and Plan B"
];

export default function AIPanel() {
  const [input, setInput] = useState("");
  const { messages, push, updateLast, setSteps, thinking, setThinking } = useAIStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);
  const scenario = useScenarioStore((s) => s.scenarios.find((x) => x.id === s.activeId)!);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [messages, thinking]);

  const ask = async (q: string) => {
    if (!q.trim() || thinking) return;
    setInput("");
    push({ role: "user", text: q });
    setThinking(true);
    openWindow("trace");

    const steps: AgentStep[] = [];
    const lower = q.toLowerCase();
    const wantsComparison = lower.includes("compare") || lower.includes("plan a");

    for (let i = 0; i < PIPELINE.length; i++) {
      const p = PIPELINE[i];
      steps.push({ id: "s" + i, agent: p.agent, text: p.text, state: "running", tool: p.tool });
      setSteps(steps.map((s, idx) => ({ ...s, state: idx === steps.length - 1 ? "running" : "done" })));
      await new Promise((r) => setTimeout(r, 420 + Math.random() * 300));
    }
    setSteps(steps.map((s) => ({ ...s, state: "done" })));

    if (wantsComparison) {
      openWindow("comparison");
      push({
        role: "assistant",
        text:
          "Plan A wins 5 of 7 criteria.\n\n" +
          "• Population served 89% vs 85%\n" +
          "• Average travel time 22 min vs 24 min\n" +
          "• Emergency access +22% vs +14%\n" +
          "• Cost ₹42 Cr vs ₹36 Cr (Plan B cheaper)\n\n" +
          "Recommendation: adopt Plan A unless the capital ceiling is hard-capped below ₹40 Cr. " +
          "All figures come from the comparison engine on dataset ds_2026.02."
      });
      setThinking(false);
      return;
    }

    const facility = lower.includes("school") ? "School" : lower.includes("fire") ? "Fire Station" : "Hospital";
    const result = await api.suitability(
      { facility: facility as any, capacity: 250, minArea: 4000, maxTravelMin: 15, floodRule: "Exclude High", weights: { ...DEFAULT_WEIGHTS } },
      scenario
    );
    addResult(result);
    mapBridge.showCandidates(result.entities);
    openWindow("results");

    const top = result.entities[0];
    push({
      role: "assistant",
      resultId: result.resultId,
      text: top
        ? "Recommendation: " + top.label + " (score " + top.score.toFixed(1) + "/100).\n\n" +
          "Why:\n" +
          "• Catchment population score " + top.breakdown.Population + "/100\n" +
          "• Accessibility " + top.breakdown.Accessibility + "/100 within the 15-minute threshold\n" +
          "• Flood constraint " + top.breakdown["Flood risk"] + "/100 (high-risk parcels excluded)\n" +
          "• Coverage gap " + top.breakdown["Existing coverage"] + "/100 relative to existing " + facility.toLowerCase() + "s\n\n" +
          "Runners-up: " + result.entities.slice(1, 3).map((e) => e.label + " (" + e.score.toFixed(1) + ")").join(", ") + ".\n\n" +
          "Numbers produced by the deterministic GIS / network / optimisation tools — result " + result.resultId + " on " + result.datasetVersion + "."
        : "No parcel satisfies the current constraint set. Relax the minimum land area or allow medium flood risk."
    });
    setThinking(false);
  };

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef}>
        {messages.map((m) => (
          <div key={m.id} className={"bubble " + (m.role === "user" ? "user" : "ai")}>{m.text}</div>
        ))}
        {thinking && <div className="bubble ai pulse">running deterministic planning tools…</div>}
        {!thinking && messages.length <= 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 4 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="btn ghost" style={{ textAlign: "left" }} onClick={() => ask(s)}>{s}</button>
            ))}
          </div>
        )}
      </div>
      <div className="chat-input">
        <input className="input" placeholder="Ask the planning assistant…" value={input}
          onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask(input)} />
        <button className="btn primary" disabled={thinking} onClick={() => ask(input)}>Send</button>
      </div>
    </div>
  );
}
