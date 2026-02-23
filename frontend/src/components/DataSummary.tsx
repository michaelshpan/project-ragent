import { renderMarkdown } from "../utils/markdown";

interface Props {
  summaries: Record<string, string>;
}

export function DataSummary({ summaries }: Props) {
  return (
    <div className="data-summary fade-in">
      <h2>Market Data Collected</h2>
      {Object.entries(summaries).map(([key, text]) => (
        <details key={key} className="summary-section">
          <summary>{key.charAt(0).toUpperCase() + key.slice(1)} Data</summary>
          <div
            className="markdown-body"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
          />
        </details>
      ))}
    </div>
  );
}
