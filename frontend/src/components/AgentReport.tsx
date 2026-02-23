import { renderMarkdown } from "../utils/markdown";

const LABELS: Record<string, string> = {
  quant: "Quantitative Valuation",
  sentiment: "Sentiment Analysis",
  technical: "Technical Signals",
};

interface Props {
  reports: Record<string, string>;
}

export function AgentReport({ reports }: Props) {
  const entries = Object.entries(reports);
  if (entries.length === 0) return null;

  return (
    <div className="agent-reports fade-in">
      <h2>Research Reports</h2>
      <div className="report-grid">
        {entries.map(([key, text]) => (
          <div key={key} className="report-card">
            <h3>{LABELS[key] ?? key}</h3>
            <div
              className="markdown-body"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
