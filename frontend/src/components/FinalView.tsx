import { renderMarkdown } from "../utils/markdown";
import type { AnalysisState, SourceEntry } from "../types/analysis";

interface Props {
  state: AnalysisState;
  onNewAnalysis: () => void;
}

export function FinalView({ state, onNewAnalysis }: Props) {
  const { finalDecision, allReports, dataSummaries, sourceLog, ticker, elapsed } = state;
  if (!finalDecision) return null;

  // Determine BUY/SELL from final decision text
  const firstLine = finalDecision.split("\n").find((l) => l.trim()) ?? "";
  const isBuy = /\bBUY\b/i.test(firstLine);

  return (
    <div className="final-view fade-in">
      <div className={`hero-decision ${isBuy ? "buy" : "sell"}`}>
        <h1>{ticker}</h1>
        <div className="hero-verdict">{isBuy ? "BUY" : "SELL"}</div>
        <div
          className="hero-details markdown-body"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(finalDecision) }}
        />
        <p className="hero-elapsed">Completed in {elapsed}s</p>
      </div>

      <div className="details-sections">
        {allReports && (
          <>
            <details className="report-details">
              <summary>Quantitative Valuation Research</summary>
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(allReports.quant) }} />
            </details>
            <details className="report-details">
              <summary>Sentiment Research</summary>
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(allReports.sentiment) }} />
            </details>
            <details className="report-details">
              <summary>Technical Signals Research</summary>
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(allReports.technical) }} />
            </details>
            <details className="report-details">
              <summary>Portfolio Manager Decision (Stage 2)</summary>
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(allReports.pm_decision) }} />
            </details>
            <details className="report-details">
              <summary>Devil's Advocate Challenge</summary>
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(allReports.da_challenge) }} />
            </details>
          </>
        )}

        {dataSummaries && (
          <details className="report-details">
            <summary>Raw Data Summaries</summary>
            {Object.entries(dataSummaries).map(([key, text]) => (
              <div key={key}>
                <h4>{key.charAt(0).toUpperCase() + key.slice(1)}</h4>
                <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />
              </div>
            ))}
          </details>
        )}

        {sourceLog.length > 0 && (
          <details className="report-details">
            <summary>Data Sources ({sourceLog.length})</summary>
            <SourceTable entries={sourceLog} />
          </details>
        )}
      </div>

      <button onClick={onNewAnalysis} className="new-analysis-btn">
        Start New Analysis
      </button>
    </div>
  );
}

function SourceTable({ entries }: { entries: SourceEntry[] }) {
  return (
    <div className="source-table-wrapper">
      <table className="source-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Type</th>
            <th>URL</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={i}>
              <td>{e.source}</td>
              <td>{e.type}</td>
              <td className="url-cell">{e.url.length > 60 ? e.url.slice(0, 57) + "..." : e.url}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
