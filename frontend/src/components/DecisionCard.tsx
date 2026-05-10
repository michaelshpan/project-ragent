import { renderMarkdown } from "../utils/markdown";
import { DebugPanel } from "./DebugPanel";
import type { DebugInfo } from "../types/analysis";

interface Props {
  title: string;
  content: string;
  demoMode?: boolean;
  debug?: DebugInfo;
}

export function DecisionCard({ title, content, demoMode, debug }: Props) {
  const isBuy = /\bBUY\b/i.test(content) && !/\bSELL\b/i.test(content.split("\n")[0]);

  return (
    <div className={`decision-card fade-in ${isBuy ? "buy" : "sell"}`}>
      <h2>{title}</h2>
      <div
        className="markdown-body"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
      />
      {demoMode && <DebugPanel debug={debug} done />}
    </div>
  );
}
