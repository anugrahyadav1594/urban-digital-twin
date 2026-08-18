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

const SUGGESTIONS = [
  "Where should we build a new hospital?",
  "Which wards are underserved by emergency services?",
  "Compare Plan A and Plan B"
];

export default function AIPanel() {
  const [input, setInput] = useState("");
  const { messages, push, setSteps, thinking, setThinking } = useAIStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);
  const { scenarios, activeId } = useScenarioStore();
  const scenario = scenarios.find((x) => x.id === activeId) ?? scenarios[0] ?? { id: "1", name: "Base City" };
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [messages, thinking]);

  const ask = async (q: string) => {
    if (!q.trim() || thinking) return;
    setInput("");
    push({ role: "user", text: q });
    setThinking(true);
    openWindow("trace");

    const lower = q.toLowerCase();
    const wantsComparison = lower.includes("compare") || lower.includes("plan a") || lower.includes("plan b");

    if (wantsComparison && scenarios.length >= 2) {
      try {
        const idA = scenarios[0].id;
        const idB = scenarios[1].id;
        const comp = await api.compareScenarios([idA, idB]);
        openWindow("comparison");
        const winner = comp?.entities?.[0]?.label ?? scenarios[0].name;
        push({
          role: "assistant",
          text: `Backend Scenario Comparison Result:\n\n${comp?.explanation ?? "Comparison finished."}\n\nTop Scenario: ${winner}`
        });
      } catch (err: any) {
        push({ role: "assistant", text: `Comparison failed: ${err.message || "Backend error"}` });
      } finally {
        setThinking(false);
      }
      return;
    }

    try {
      const agentRes = await api.agentPlan(q);
      if (agentRes) {
        if (agentRes.steps && Array.isArray(agentRes.steps)) {
          setSteps(agentRes.steps as AgentStep[]);
        }
        push({
          role: "assistant",
          resultId: agentRes.result_id,
          text: agentRes.report || "AI Plan complete."
        });
        setThinking(false);
        return;
      }
    } catch (e: any) {
      console.warn("Backend AI service error:", e);
      push({ role: "assistant", text: `AI Planning error: ${e.message || "Failed to execute AI plan on backend."}` });
      setThinking(false);
      return;
    }

    // Fallback deterministic suitability analysis using live backend
    try {
      const facility = lower.includes("school") ? "School" : lower.includes("fire") ? "Fire Station" : "Hospital";
      const result = await api.suitability(
        { facility: facility as any, capacity: 250, minArea: 4000, maxTravelMin: 15, floodRule: "Exclude High", weights: { ...DEFAULT_WEIGHTS } },
        scenario
      );
      addResult(result);
      if (result.entities && result.entities.length > 0) {
        mapBridge.showCandidates(result.entities);
      }
      openWindow("results");

      const top = result.entities?.[0];
      push({
        role: "assistant",
        resultId: result.resultId,
        text: top
          ? `Recommendation: ${top.label} (score ${top.score.toFixed(1)}/100).\n\n${result.explanation}`
          : "No parcel satisfies the current constraint set."
      });
    } catch (err: any) {
      push({ role: "assistant", text: `Analysis failed: ${err.message || "Backend unreachable"}` });
    } finally {
      setThinking(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef}>
        {messages.map((m) => (
          <div key={m.id} className={"bubble " + (m.role === "user" ? "user" : "ai")}>{m.text}</div>
        ))}
        {thinking && <div className="bubble ai pulse">running backend AI & deterministic planning pipeline…</div>}
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
