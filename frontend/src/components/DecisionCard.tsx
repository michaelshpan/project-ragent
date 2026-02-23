import { renderMarkdown } from "../utils/markdown";

interface Props {
  title: string;
  content: string;
}

export function DecisionCard({ title, content }: Props) {
  const isBuy = /\bBUY\b/i.test(content) && !/\bSELL\b/i.test(content.split("\n")[0]);

  return (
    <div className={`decision-card fade-in ${isBuy ? "buy" : "sell"}`}>
      <h2>{title}</h2>
      <div
        className="markdown-body"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
      />
    </div>
  );
}
