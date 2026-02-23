import { useState, useEffect } from "react";

interface Props {
  onSubmit: (ticker: string) => void;
  disabled: boolean;
}

export function TickerInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");
  const [usage, setUsage] = useState<{ count: number; limit: number; remaining: number } | null>(null);

  useEffect(() => {
    fetch("/api/usage")
      .then((r) => r.json())
      .then(setUsage)
      .catch(() => {});
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (ticker && /^[A-Z]{1,5}$/.test(ticker)) {
      onSubmit(ticker);
    }
  };

  return (
    <div className="ticker-input-container">
      <h1 className="title">RAgent Investment Committee</h1>
      <p className="subtitle">
        AI-powered multi-agent stock analysis pipeline
      </p>
      <form onSubmit={handleSubmit} className="ticker-form">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="Enter ticker (e.g. AAPL)"
          maxLength={5}
          disabled={disabled}
          className="ticker-field"
          autoFocus
        />
        <button type="submit" disabled={disabled || !value.trim()} className="analyze-btn">
          Analyze
        </button>
      </form>
      {usage && (
        <UsageCounter count={usage.count} limit={usage.limit} />
      )}
    </div>
  );
}

function UsageCounter({ count, limit }: { count: number; limit: number }) {
  return (
    <div className="usage-counter">
      {count}/{limit} analyses used today
    </div>
  );
}
