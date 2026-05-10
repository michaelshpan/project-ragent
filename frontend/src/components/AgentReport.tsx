import { renderMarkdown } from "../utils/markdown";
import { DebugPanel } from "./DebugPanel";
import type { DebugInfo } from "../types/analysis";

const RESEARCH_KEYS = ["quant", "sentiment", "technical"] as const;

const LABELS: Record<string, string> = {
  quant: "Quantitative Valuation",
  sentiment: "Sentiment Analysis",
  technical: "Technical Signals",
};

interface Props {
  reports: Record<string, string>;
  demoMode?: boolean;
  debug?: Record<string, DebugInfo>;
}

export function AgentReport({ reports, demoMode, debug }: Props) {
  // Demo mode: render all three slots so prompts and live status are visible
  // even before any agent has finished. Clean mode: render only completed.
  const entries = demoMode
    ? RESEARCH_KEYS.map((k) => [k, reports[k] ?? null] as const)
    : Object.entries(reports).map(([k, v]) => [k, v] as const);

  if (entries.length === 0) return null;

  return (
    <div className="agent-reports fade-in">
      <h2>Research Reports</h2>
      <div className="report-grid">
        {entries.map(([key, text]) => (
          <div key={key} className="report-card">
            <h3>{LABELS[key] ?? key}</h3>
            {text ? (
              <div
                className="markdown-body"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
              />
            ) : (
              <div className="report-pending">
                <span className="spinner-small" />
                <span>Analyzing…</span>
              </div>
            )}
            {demoMode && <DebugPanel debug={debug?.[key]} done={!!text} />}
          </div>
        ))}
      </div>
    </div>
  );
}
