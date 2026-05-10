export type Stage =
  | "idle"
  | "data_fetch"
  | "research"
  | "pm_decision"
  | "da_challenge"
  | "final_decision"
  | "complete"
  | "error";

export interface DebugInfo {
  model_id?: string;
  display_name?: string;
  system_prompt?: string;
  user_prompt?: string;
  thinking?: string | null;
  duration_ms?: number;
  error?: string;
}

export interface SSEEvent {
  event: string;
  stage?: string;
  message?: string;
  elapsed?: number;
  summary?: Record<string, string>;
  current_price?: number | null;
  agent?: string;
  report?: string;
  content?: string;
  source_log?: SourceEntry[];
  all_reports?: AllReports;
  data_summaries?: Record<string, string>;
  debug?: DebugInfo;
  all_debug?: Record<string, DebugInfo>;
}

export interface SourceEntry {
  source: string;
  type: string;
  url: string;
  timestamp: string;
}

export interface AllReports {
  quant: string;
  sentiment: string;
  technical: string;
  pm_decision: string;
  da_challenge: string;
  final_decision: string;
}

export interface AnalysisState {
  stage: Stage;
  ticker: string;
  message: string;
  currentPrice: number | null;
  dataSummaries: Record<string, string> | null;
  agentReports: Record<string, string>;
  pmDecision: string | null;
  daChallenge: string | null;
  finalDecision: string | null;
  sourceLog: SourceEntry[];
  allReports: AllReports | null;
  elapsed: number;
  error: string | null;
  demoMode: boolean;
  debug: Record<string, DebugInfo>;
}

export const INITIAL_STATE: AnalysisState = {
  stage: "idle",
  ticker: "",
  message: "",
  currentPrice: null,
  dataSummaries: null,
  agentReports: {},
  pmDecision: null,
  daChallenge: null,
  finalDecision: null,
  sourceLog: [],
  allReports: null,
  elapsed: 0,
  error: null,
  demoMode: false,
  debug: {},
};
