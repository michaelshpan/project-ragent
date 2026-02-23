import { renderMarkdown } from "../utils/markdown";
import { downloadMarkdown, buildFullReport } from "../utils/download";
import type { AnalysisState, SourceEntry } from "../types/analysis";

interface Props {
  state: AnalysisState;
  onNewAnalysis: () => void;
}

const SECTION_TITLES: Record<string, string> = {
  quant: "Quantitative Valuation Research \u2014 Grok 4.1",
  sentiment: "Sentiment Research \u2014 GLM-5",
  technical: "Technical Signals Research \u2014 Kimi K2.5",
  pm_decision: "Portfolio Manager Initial Decision \u2014 Claude Opus 4.6",
  da_challenge: "Devil's Advocate Challenge \u2014 Claude Sonnet 4.6",
};

function downloadSection(title: string, content: string, ticker: string) {
  const slug = title.replace(/[^a-zA-Z0-9]+/g, "_").toLowerCase();
  downloadMarkdown(`# ${title}\n\n${content}`, `${ticker}_${slug}.md`);
}

export function FinalView({ state, onNewAnalysis }: Props) {
  const { finalDecision, allReports, dataSummaries, sourceLog, ticker, elapsed, currentPrice } = state;
  if (!finalDecision) return null;

  // Determine BUY/SELL from the "Decision: BUY/SELL" line in final decision text
  const decisionLine = finalDecision.split("\n").find((l) => /decision:\s*(BUY|SELL)/i.test(l));
  const isBuy = decisionLine ? /decision:\s*BUY/i.test(decisionLine) : /\bBUY\b/i.test(finalDecision);

  const handleFullDownload = () => {
    if (!allReports) return;
    const ts = new Date().toISOString().replace(/[:.]/g, "").slice(0, 15);
    const content = buildFullReport(ticker, allReports, sourceLog);
    downloadMarkdown(content, `${ticker}_${ts}.md`);
  };

  return (
    <div className="final-view fade-in">
      <div className={`hero-decision ${isBuy ? "buy" : "sell"}`}>
        <h1>Final Investment Decision: {ticker}</h1>
        <p className="hero-model">Claude Opus 4.6</p>
        {currentPrice != null && (
          <p className="hero-price">Current Price: ${currentPrice.toFixed(2)}</p>
        )}
        <div className="hero-verdict">{isBuy ? "BUY" : "SELL"}</div>
        <div
          className="hero-details markdown-body"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(finalDecision) }}
        />
        <p className="hero-elapsed">Completed in {elapsed}s</p>
      </div>

      <div className="download-toolbar">
        <button onClick={handleFullDownload} className="download-btn" disabled={!allReports}>
          Download Full Report
        </button>
      </div>

      <div className="details-sections">
        {allReports && (
          <>
            {(
              [
                ["quant", allReports.quant],
                ["sentiment", allReports.sentiment],
                ["technical", allReports.technical],
                ["pm_decision", allReports.pm_decision],
                ["da_challenge", allReports.da_challenge],
              ] as const
            ).map(([key, content]) => (
              <details key={key} className="report-details">
                <summary>{SECTION_TITLES[key]}</summary>
                <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />
                <button
                  className="download-section-btn"
                  onClick={() => downloadSection(SECTION_TITLES[key], content, ticker)}
                >
                  Download Section
                </button>
              </details>
            ))}
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
              <td className="url-cell">
                <a href={e.url} target="_blank" rel="noopener noreferrer">
                  {e.url.length > 60 ? e.url.slice(0, 57) + "..." : e.url}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
