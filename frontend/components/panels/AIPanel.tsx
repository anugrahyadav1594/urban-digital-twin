"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { DEFAULT_WEIGHTS } from "@/lib/mock";
import { mapBridge } from "@/cesium/map-bridge";
import { useAIStore } from "@/stores/ai-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import NextAction from "@/components/workflow/NextAction";
import type { AgentStep } from "@/types";

const SUGGESTIONS = [
  "Explain current recommendation & trade-offs",
  "Where should we build a new hospital?",
  "Which wards are underserved by emergency services?",
  "Compare Plan A and Plan B"
];

export default function AIPanel() {
  const [input, setInput] = useState("");
  const { messages, push, setSteps, thinking, setThinking } = useAIStore();
  const { results, activeId: activeResultId } = useAnalysisStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);
  const { scenarios, activeId } = useScenarioStore();
  const scenario = scenarios.find((x) => x.id === activeId) ?? scenarios[0] ?? { id: "1", name: "Base City" };
  const logRef = useRef<HTMLDivElement>(null);

  const activeResult = results.find((r) => r.resultId === activeResultId) ?? results[0] ?? null;

  useEffect(() => { logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [messages, thinking]);

  const explainActiveResult = async () => {
    if (!activeResult) {
      push({
        role: "assistant",
        text: "No active analysis result is currently loaded. Please run a site suitability, accessibility, or disaster simulation first."
      });
      return;
    }

    setThinking(true);
    try {
      const { useWorkflowStore } = await import("@/stores/workflow-store");
      const workflowStore = useWorkflowStore.getState();
      let sessId = workflowStore.context.backendSessionId;
      if (!sessId) {
        const startRes = await api.startWorkflow("explain", scenario.id);
        workflowStore.syncFromBackend(startRes);
        sessId = startRes.session_id;
      }

      const rec = await api.explainDecisionRecord({
        session_id: sessId,
        result_id: activeResult.resultId,
        scenario_id: scenario.id
      });

      const scoreBreakdownText = Object.entries(rec.score_breakdown || {})
        .map(([k, v]) => `${k}: ${v.toFixed(1)}`)
        .join("\n• ");

      const explanationText = `### Grounded Decision Record

**Primary Recommendation:** ${rec.recommendation || "N/A"}
${rec.overall_score != null ? `**Overall Composite Score:** ${rec.overall_score.toFixed(1)} / 100\n` : ""}
**Dataset Version:** \`${rec.provenance?.dataset_version || "v1"}\` | **Scenario Version:** \`${rec.scenario_id || scenario.id}\`

${scoreBreakdownText ? `#### Criteria Score Breakdown:\n• ${scoreBreakdownText}\n` : ""}
${rec.benefits?.length ? `#### Benefits:\n• ${rec.benefits.join("\n• ")}\n` : ""}
${rec.tradeoffs?.length ? `#### Trade-offs:\n• ${rec.tradeoffs.join("\n• ")}\n` : ""}
${rec.assumptions?.length ? `#### Assumptions & Rules:\n• ${rec.assumptions.join("\n• ")}\n` : ""}
${rec.limitations?.length ? `#### Limitations:\n• ${rec.limitations.join("\n• ")}` : ""}`;

      push({
        role: "assistant",
        resultId: activeResult.resultId,
        text: explanationText
      });
    } catch (err: any) {
      console.error("Explain decision record failed:", err);
      push({
        role: "assistant",
        text: `Failed to generate decision record from backend: ${err.message || "Unknown backend error"}`
      });
    } finally {
      setThinking(false);
    }
  };

  const ask = async (q: string) => {
    if (!q.trim() || thinking) return;
    setInput("");
    push({ role: "user", text: q });

    const lower = q.toLowerCase();

    if (lower.includes("explain current") || lower.includes("explain recommendation")) {
      explainActiveResult();
      return;
    }

    setThinking(true);
    openWindow("trace");

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
      push({ role: "assistant", text: `AI Planning notice: ${e.message || "Executing deterministic fallback..."}` });
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
          ? `Grounded Recommendation: ${top.label}${top.score != null ? ` (score ${top.score.toFixed(1)}/100)` : ""}.\n\n${result.explanation}`
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
          <div key={m.id} className={"bubble " + (m.role === "user" ? "user" : "ai")} style={{ whiteSpace: "pre-wrap" }}>
            {m.text}
          </div>
        ))}
        {thinking && <div className="bubble ai pulse">orchestrating deterministic engines & running pipeline…</div>}
        {!thinking && messages.length <= 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 4 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="btn ghost" style={{ textAlign: "left", fontSize: 11.5 }} onClick={() => ask(s)}>{s}</button>
            ))}
          </div>
        )}
      </div>

      {activeResult && (
        <div style={{ padding: "0 8px 6px" }}>
          <NextAction
            title="EXPLAIN RECOMMENDATION"
            prompt={`Explain active result "${activeResult.title}" with metric breakdown and limitations.`}
            actionLabel="Generate Decision Record"
            onAction={explainActiveResult}
            targetWindow="ai"
            secondaryActionLabel="Commit to Scenario"
            secondaryTargetWindow="changes"
            variant="accent"
          />
        </div>
      )}

      <div className="chat-input">
        <input className="input" placeholder="Ask the planning assistant…" value={input}
          onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask(input)} />
        <button className="btn primary" disabled={thinking} onClick={() => ask(input)}>Send</button>
      </div>
    </div>
  );
}
