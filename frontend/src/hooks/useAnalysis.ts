import { useCallback, useRef, useReducer } from "react";
import type { AnalysisState, SSEEvent, Stage } from "../types/analysis";
import { INITIAL_STATE } from "../types/analysis";

type Action =
  | { type: "START"; ticker: string }
  | { type: "EVENT"; payload: SSEEvent }
  | { type: "RESET" };

function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case "START":
      return { ...INITIAL_STATE, stage: "data_fetch", ticker: action.ticker, message: "Starting analysis..." };
    case "RESET":
      return INITIAL_STATE;
    case "EVENT": {
      const e = action.payload;
      switch (e.event) {
        case "status":
          return { ...state, stage: (e.stage as Stage) ?? state.stage, message: e.message ?? "" };
        case "data_ready":
          return {
            ...state,
            stage: "data_fetch",
            dataSummaries: e.summary ?? null,
            elapsed: e.elapsed ?? state.elapsed,
            message: "Market data collected",
          };
        case "agent_done":
          return {
            ...state,
            agentReports: { ...state.agentReports, [e.agent!]: e.report! },
          };
        case "stage_done":
          if (e.stage === "pm_decision") return { ...state, pmDecision: e.content ?? null };
          if (e.stage === "da_challenge") return { ...state, daChallenge: e.content ?? null };
          if (e.stage === "final_decision") return { ...state, finalDecision: e.content ?? null };
          return state;
        case "complete":
          return {
            ...state,
            stage: "complete",
            elapsed: e.elapsed ?? state.elapsed,
            sourceLog: e.source_log ?? [],
            allReports: e.all_reports ?? null,
            dataSummaries: e.data_summaries ?? state.dataSummaries,
            message: "",
          };
        case "error":
          return { ...state, stage: "error", error: e.message ?? "Unknown error" };
        default:
          return state;
      }
    }
  }
}

export function useAnalysis() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async (ticker: string) => {
    // Abort any in-flight analysis
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: "START", ticker });

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        dispatch({ type: "EVENT", payload: { event: "error", message: body.detail ?? `HTTP ${res.status}` } });
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;

        for (const part of parts) {
          const dataLine = part
            .split("\n")
            .find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          try {
            const payload: SSEEvent = JSON.parse(dataLine.slice(6));
            dispatch({ type: "EVENT", payload });
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      dispatch({ type: "EVENT", payload: { event: "error", message: String(err) } });
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET" });
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET" });
  }, []);

  return { state, start, reset, cancel };
}
