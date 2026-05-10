import type { DebugInfo } from "../types/analysis";
import { renderMarkdown } from "../utils/markdown";

interface Props {
  debug: DebugInfo | undefined;
  /** Whether the agent has finished running (drives "running…" placeholders). */
  done?: boolean;
}

function MarkdownBlock({ content }: { content: string }) {
  return (
    <div
      className="debug-block debug-block-md markdown-body"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}

function formatDuration(ms: number | undefined): string | null {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function isAnthropic(displayName?: string, modelId?: string): boolean {
  const haystack = `${displayName ?? ""} ${modelId ?? ""}`.toLowerCase();
  return haystack.includes("claude") || haystack.includes("opus") || haystack.includes("sonnet") || haystack.includes("haiku");
}

export function DebugPanel({ debug, done }: Props) {
  if (!debug) return null;

  const { display_name, model_id, system_prompt, user_prompt, thinking, duration_ms, error } = debug;
  const duration = formatDuration(duration_ms);

  return (
    <details className="debug-panel">
      <summary>
        <span className="debug-panel-summary-label">Analysis trace</span>
        {display_name && (
          <span className="debug-panel-model">{display_name}</span>
        )}
        {duration && <span className="debug-panel-duration">{duration}</span>}
        {!done && !duration && (
          <span className="debug-panel-running">running…</span>
        )}
      </summary>

      <div className="debug-panel-body">
        {error && (
          <div className="debug-section debug-error">
            <div className="debug-section-label">Error</div>
            <pre className="debug-block">{error}</pre>
          </div>
        )}

        {(model_id || display_name) && (
          <div className="debug-section">
            <div className="debug-section-label">Model</div>
            <div className="debug-section-content">
              {display_name}
              {model_id && model_id !== display_name && (
                <span className="debug-model-id"> · {model_id}</span>
              )}
              {duration && <span className="debug-model-id"> · {duration}</span>}
            </div>
          </div>
        )}

        {system_prompt && (
          <div className="debug-section">
            <div className="debug-section-label">System prompt</div>
            <MarkdownBlock content={system_prompt} />
          </div>
        )}

        {user_prompt && (
          <div className="debug-section">
            <div className="debug-section-label">Input data fed to model</div>
            <MarkdownBlock content={user_prompt} />
          </div>
        )}

        {thinking ? (
          <div className="debug-section">
            <div className="debug-section-label">
              Reasoning trace
              {isAnthropic(display_name, model_id) && (
                <span className="debug-section-note"> (Anthropic-summarised)</span>
              )}
            </div>
            <MarkdownBlock content={thinking} />
          </div>
        ) : done ? (
          <div className="debug-section">
            <div className="debug-section-label">Reasoning trace</div>
            <div className="debug-section-content debug-muted">
              {isAnthropic(display_name, model_id)
                ? "Anthropic only exposes a summarised trace; this run produced no summary."
                : "No reasoning trace returned by this model."}
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
}
