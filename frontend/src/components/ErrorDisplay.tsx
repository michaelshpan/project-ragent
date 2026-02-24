interface Props {
  message: string;
  onRetry: () => void;
}

export function ErrorDisplay({ message, onRetry }: Props) {
  const isRateLimit = message.toLowerCase().includes("daily limit");

  return (
    <div className="error-display">
      <h2>{isRateLimit ? "That's a Wrap for Today" : "Analysis Failed"}</h2>
      <p className="error-message">{message}</p>
      <button onClick={onRetry} className="retry-btn">
        {isRateLimit ? "Back to Home" : "Try Again"}
      </button>
    </div>
  );
}
