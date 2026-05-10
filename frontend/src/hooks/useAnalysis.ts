import { useCallback, useEffect, useRef, useReducer, useState } from "react";
import type { AnalysisState, DebugInfo, SSEEvent, Stage } from "../types/analysis";
import { INITIAL_STATE } from "../types/analysis";

const DEMO_MODE_KEY = "ragent.demoMode";

function readDemoMode(): boolean {
  try {
    return window.localStorage.getItem(DEMO_MODE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDemoMode(value: boolean) {
  try {
    window.localStorage.setItem(DEMO_MODE_KEY, value ? "1" : "0");
  } catch {
    // ignore — non-critical
  }
}

function debugKey(e: SSEEvent): string | null {
  if (e.agent) return e.agent;
  if (e.stage) return e.stage;
  return null;
}

type Action =
  | { type: "START"; ticker: string; demoMode: boolean }
  | { type: "EVENT"; payload: SSEEvent }
  | { type: "RESET" }
  | { type: "SET_DEMO_MODE"; demoMode: boolean };

function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case "START":
      return {
        ...INITIAL_STATE,
        demoMode: action.demoMode,
        stage: "data_fetch",
        ticker: action.ticker,
        message: "Starting analysis...",
      };
    case "RESET":
      return { ...INITIAL_STATE, demoMode: state.demoMode };
    case "SET_DEMO_MODE":
      return { ...state, demoMode: action.demoMode };
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
            currentPrice: e.current_price ?? null,
            elapsed: e.elapsed ?? state.elapsed,
            message: "Market data collected",
          };
        case "agent_started": {
          const key = debugKey(e);
          if (!key || !e.debug) return state;
          return { ...state, debug: { ...state.debug, [key]: { ...state.debug[key], ...e.debug } } };
        }
        case "agent_done": {
          const key = debugKey(e);
          const nextDebug = key && e.debug
            ? { ...state.debug, [key]: { ...state.debug[key], ...e.debug } }
            : state.debug;
          return {
            ...state,
            agentReports: { ...state.agentReports, [e.agent!]: e.report! },
            debug: nextDebug,
          };
        }
        case "stage_done": {
          const key = debugKey(e);
          const nextDebug = key && e.debug
            ? { ...state.debug, [key]: { ...state.debug[key], ...e.debug } }
            : state.debug;
          if (e.stage === "pm_decision") return { ...state, pmDecision: e.content ?? null, debug: nextDebug };
          if (e.stage === "da_challenge") return { ...state, daChallenge: e.content ?? null, debug: nextDebug };
          if (e.stage === "final_decision") return { ...state, finalDecision: e.content ?? null, debug: nextDebug };
          return { ...state, debug: nextDebug };
        }
        case "complete": {
          const merged: Record<string, DebugInfo> = { ...state.debug };
          if (e.all_debug) {
            for (const [k, v] of Object.entries(e.all_debug)) {
              merged[k] = { ...merged[k], ...v };
            }
          }
          return {
            ...state,
            stage: "complete",
            elapsed: e.elapsed ?? state.elapsed,
            sourceLog: e.source_log ?? [],
            allReports: e.all_reports ?? null,
            dataSummaries: e.data_summaries ?? state.dataSummaries,
            debug: merged,
            message: "",
          };
        }
        case "error":
          return { ...state, stage: "error", error: e.message ?? "Unknown error" };
        default:
          return state;
      }
    }
  }
}

export function useAnalysis() {
  const [demoMode, setDemoModeState] = useState<boolean>(readDemoMode);
  const [state, dispatch] = useReducer(reducer, { ...INITIAL_STATE, demoMode: readDemoMode() });
  const abortRef = useRef<AbortController | null>(null);

  // Keep reducer state in sync with hook state when toggle flips between runs.
  useEffect(() => {
    dispatch({ type: "SET_DEMO_MODE", demoMode });
    writeDemoMode(demoMode);
  }, [demoMode]);

  const setDemoMode = useCallback((v: boolean) => {
    setDemoModeState(v);
  }, []);

  const start = useCallback(async (ticker: string) => {
    // Abort any in-flight analysis
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const currentDemoMode = readDemoMode();
    dispatch({ type: "START", ticker, demoMode: currentDemoMode });

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, demo_mode: currentDemoMode }),
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

  return { state, start, reset, cancel, demoMode, setDemoMode };
}
